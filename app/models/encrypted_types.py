from sqlalchemy.types import Text, TypeDecorator

from app.crypto import decrypt_int, decrypt_json, decrypt_text, encrypt_int, encrypt_json, encrypt_text


class EncryptedString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_text(value)

    def process_result_value(self, value, dialect):
        return decrypt_text(value)


EncryptedText = EncryptedString


class EncryptedInteger(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_int(value)

    def process_result_value(self, value, dialect):
        return decrypt_int(value)


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_json(value)

    def process_result_value(self, value, dialect):
        return decrypt_json(value)
