class BigRigError(Exception):
    pass


class SettingsNotConfigured(BigRigError):
    pass


class NotAvailable(BigRigError):
    pass
