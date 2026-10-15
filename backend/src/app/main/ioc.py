from dishka import Container, Provider, Scope, make_container, provide

from app.main.settings import Settings


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def provide_settings(self) -> Settings:
        return Settings()


def create_container() -> Container:
    return make_container(SettingsProvider())
