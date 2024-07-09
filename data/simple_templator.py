import json
import traceback
import re

import utils


class SimpleTemplator:
    all_languages = []

    def __init__(self, path, language='en'):
        self.templates = {}
        self.language = language
        with open(path, 'r', encoding='utf-8') as f:
            self.templates = json.load(f)

        # получаем все языки
        for key in self.templates:
            for lang in self.templates[key]:
                if lang not in self.all_languages:
                    self.all_languages.append(lang)

        no_language = {}
        for key in self.templates:
            for lang in self.all_languages:
                if lang not in self.templates[key]:
                    if key in no_language:
                        no_language[key].append(lang)
                    else:
                        no_language[key] = [lang]

        for key in no_language:
            utils.log_error(f"MessageTemplate error: key <{key}> no language {no_language[key]} {self.templates[key]}")

        invalid_args = {}
        invalid_replaces = {}
        for key in self.templates:
            args_count = {}
            replace_count = {}
            for lang in self.all_languages:
                if lang in self.templates[key]:
                    args_match = re.findall(r'\{\d+\}', self.templates[key][lang])
                    args_count[lang] = args_match
                    repalce_match = re.findall(r'\[\[(.*?)\]\]', self.templates[key][lang])
                    replace_count[lang] = repalce_match
            count = 0
            for lang in args_count:
                if count == 0:
                    count = args_count[lang]
                if count != args_count[lang]:
                    invalid_args[f"{key}.{lang}"] = count

            count = 0
            for lang in replace_count:
                if count == 0:
                    count = replace_count[lang]
                if count != replace_count[lang]:
                    invalid_replaces[f"{key}.{lang}"] = count

        for key in invalid_args:
            utils.log_error(f"MessageTemplate error: invalid args key <{key}> or other language... count {invalid_args[key]}")

        for key in invalid_replaces:
            utils.log_error(f"MessageTemplate error: invalid replaces key <{key}> or other language... count {invalid_replaces[key]}")

        self.replace_fields()

    def replace_fields(self):
        for key in self.templates:
            for lang in self.templates[key]:
                self.templates[key][lang] = self.apply_field_values(self.templates[key][lang], lang)

    def apply_field_values(self, message: str, lang: str) -> str:
        matches = re.findall(r'\[\[(.*?)\]\]', message)
        for match in matches:
            if match in self.templates:
                message = message.replace(f'[[{match}]]', self.templates[match][lang])
        return message

    def get(self, key, *args):
        if key not in self.templates:
            return f'Template key {key} not found!'

        if self.language not in self.templates[key]:
            return f'Language {self.language} by {key} not found!'

        message_template = self.templates[key][self.language]
        try:
            template_format = message_template.format(*args)
        except Exception:
            matches = re.findall(r'\{\d+\}', message_template)
            utils.log_error(f"MessageTemplate.get error: language <{self.language}> | key: <{key}> args: <{len(args)}/{len(matches)}>\n{traceback.print_stack()}")
            template_format = "no value"
        return template_format

# template_engine = MessageTemplate('messages.json')
