import ipaddress
import os
import shutil
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


class CertificateManager:
    def __init__(self, config):
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.cert_file = Path(self.config.get("cert_file", "web/certs/selfsigned/fullchain.pem"))
        self.key_file = Path(self.config.get("key_file", "web/certs/selfsigned/privkey.pem"))
        self.common_name = self._normalize_domain_name(self.config.get("common_name", "localhost"))
        self.alt_names = [
            normalized
            for normalized in (
                self._normalize_domain_name(name)
                for name in self.config.get("alt_names", [self.common_name])
            )
            if normalized
        ]
        self.valid_days = int(self.config.get("valid_days", 365))
        self.renew_before_days = int(self.config.get("renew_before_days", 30))
        self.create_self_signed = self.config.get("create_self_signed", True)
        self.letsencrypt_enabled = self.config.get("letsencrypt_enabled", False)
        self.email = self.config.get("email", "")
        self.webroot = Path(self.config.get("webroot", "web/webroot"))
        self.certbot_config_dir = Path(self.config.get("certbot_config_dir", "web/certs"))
        self.certbot_work_dir = Path(self.config.get("certbot_work_dir", "web/certs/work"))
        self.certbot_logs_dir = Path(self.config.get("certbot_logs_dir", "web/certs/logs"))
        self.force_renewal = self.config.get("force_renewal", False)
        self.certbot_timeout_seconds = int(self.config.get("certbot_timeout_seconds", 300))

    def prepare_ssl_context(self):
        if not self.enabled:
            self._log("SSL disabled by config")
            return None

        self._log(f"checking certificate: cert={self.cert_file}, key={self.key_file}")
        cert_state = self.check_certificate()
        if cert_state["valid"]:
            self._log(f"certificate is valid until {cert_state['not_after'].isoformat()}")
        else:
            self._log(f"certificate is not ready: {cert_state['reason']}")
            if self.letsencrypt_enabled:
                self.renew_certificate()
                cert_state = self.check_certificate()
                if cert_state["valid"]:
                    self._log(f"certificate renewed and valid until {cert_state['not_after'].isoformat()}")

            if not cert_state["valid"]:
                if not self.create_self_signed:
                    self._log("certificate creation fallback disabled; HTTPS will not start")
                    return None

                self.create_certificate()
                cert_state = self.check_certificate()
                if not cert_state["valid"]:
                    self._log(f"certificate creation failed: {cert_state['reason']}")
                    return None
                self._log(f"certificate created and valid until {cert_state['not_after'].isoformat()}")

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(str(self.cert_file), str(self.key_file))
        self._log("SSL context is ready")
        return context

    def check_certificate(self):
        if not self.cert_file.is_file():
            return {"valid": False, "reason": "certificate file is missing", "not_after": None}
        if not self.key_file.is_file():
            return {"valid": False, "reason": "private key file is missing", "not_after": None}

        try:
            from cryptography import x509
        except ImportError:
            return {"valid": False, "reason": "cryptography package is not installed", "not_after": None}

        try:
            cert = x509.load_pem_x509_certificate(self.cert_file.read_bytes())
            not_after = self._get_not_after(cert)
        except Exception as error:
            return {"valid": False, "reason": f"cannot read certificate: {error}", "not_after": None}

        renew_at = datetime.now(timezone.utc) + timedelta(days=self.renew_before_days)
        if not_after <= renew_at:
            return {
                "valid": False,
                "reason": f"certificate expires soon: {not_after.isoformat()}",
                "not_after": not_after,
            }

        return {"valid": True, "reason": "", "not_after": not_after}

    def create_certificate(self):
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
        except ImportError as error:
            self._log(f"cannot create certificate: {error}")
            return

        self._log(f"creating self-signed certificate for {self.common_name}")
        now = datetime.now(timezone.utc)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
        ])

        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=self.valid_days))
            .add_extension(
                x509.SubjectAlternativeName(self._make_alt_names(x509)),
                critical=False,
            )
        )
        cert = cert_builder.sign(key, hashes.SHA256())

        self.cert_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        self.cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.key_file.chmod(0o600)
        self.cert_file.chmod(0o644)
        self._log(f"self-signed certificate files written: cert={self.cert_file}, key={self.key_file}")

    def renew_certificate(self):
        if not self.email:
            self._log("cannot request Let's Encrypt certificate: email is missing")
            return
        if shutil.which("certbot") is None:
            self._log("cannot request Let's Encrypt certificate: certbot is not installed")
            return

        domains = self._certbot_domains()
        if not domains:
            self._log("cannot request Let's Encrypt certificate: no DNS domain names configured")
            return

        self.webroot.mkdir(parents=True, exist_ok=True)
        self.certbot_config_dir.mkdir(parents=True, exist_ok=True)
        self.certbot_work_dir.mkdir(parents=True, exist_ok=True)
        self.certbot_logs_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "certbot",
            "certonly",
            "--webroot",
            "-w",
            str(self.webroot),
            "--config-dir",
            str(self.certbot_config_dir),
            "--work-dir",
            str(self.certbot_work_dir),
            "--logs-dir",
            str(self.certbot_logs_dir),
            "--non-interactive",
            "--agree-tos",
            "--email",
            self.email,
        ]
        for domain in domains:
            command.extend(["-d", domain])

        if self.force_renewal or os.getenv("MAKE_CERT", "n").lower() == "y":
            command.append("--force-renewal")
        else:
            command.append("--keep-until-expiring")

        self._log(f"requesting Let's Encrypt certificate for {', '.join(domains)}")
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.certbot_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self._log("Let's Encrypt certificate request timed out")
            return
        except Exception as error:
            self._log(f"Let's Encrypt certificate request failed: {error}")
            return

        if result.returncode == 0:
            self._log("Let's Encrypt certificate request completed")
            return

        error_output = (result.stderr or result.stdout or "").strip()
        self._log(f"Let's Encrypt certificate request failed: {error_output}")

    def _certbot_domains(self):
        domains = []
        for name in [self.common_name, *self.alt_names]:
            if not name:
                continue
            try:
                ipaddress.ip_address(name)
                continue
            except ValueError:
                pass
            if name not in domains:
                domains.append(name)
        return domains

    @staticmethod
    def _normalize_domain_name(name):
        name = str(name or "").strip()
        if not name:
            return ""

        parsed = urlparse(name if "://" in name else f"//{name}")
        hostname = parsed.hostname
        if hostname:
            return hostname.lower()
        return name.split("/", 1)[0].split(":", 1)[0].lower()

    def _make_alt_names(self, x509):
        alt_names = []
        for name in self.alt_names:
            try:
                alt_names.append(x509.IPAddress(ipaddress.ip_address(name)))
            except ValueError:
                alt_names.append(x509.DNSName(name))
        return alt_names

    @staticmethod
    def _get_not_after(cert):
        not_after = getattr(cert, "not_valid_after_utc", None)
        if not_after is None:
            not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
        return not_after

    @staticmethod
    def _log(message):
        print(f".certificate_manager {message}", flush=True)
