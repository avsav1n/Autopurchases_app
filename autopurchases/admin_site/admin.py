import functools
from copy import deepcopy

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest


class CustomAdminSite(admin.AdminSite):
    """Class кастомного сайта администратора.

    Изменения:
    - добавлена возможность переопределять порядок и группировку отображений зарегистрированных на
        сайте администратора моделей приложений, используемых в проекте. Для этого в settings.py
        необходимо описать параметр ADMIN_REORDER (логика частично основана на библиотеке
        django-modeladmin-reorder).
        Пример конфигурации ADMIN_REORDER:
            ADMIN_REORDER = (
                # сохранить оригинальное название приложения и модели
                "auth",

                # переименовать приложение
                {
                    "app": "auth",
                    "label": "Custom authorization"
                },

                # перегруппировать модели в приложении (доступно добавление моделей
                # из других приложений)
                {
                    "app": "auth",
                    "models": ("app.User", "auth.Group")
                },
            )
    """

    def __init__(self, *args, **kwargs):
        self.apps_markup: list | None = None
        super().__init__(*args, **kwargs)

    def get_app_list(self, request: HttpRequest, app_label=None):
        if self.apps_markup is not None:
            return self.apps_markup

        if not hasattr(settings, "ADMIN_REORDER"):
            # Если ADMIN_REORDER отсутствует в setting.py, модели отображаются в стандартном,
            # порядке, отсортированном лексиграфически
            return super().get_app_list(request)

        # Иначе отображаются модели, определенные в ADMIN_REORDER
        apps_dict: dict[str | dict] = self._build_app_dict(request, app_label)
        apps_config: list | tuple = settings.ADMIN_REORDER
        if not isinstance(apps_config, (list, tuple)):
            raise ImproperlyConfigured(
                f"ADMIN_REORDER config parameter must be tuple or list. Got {type(apps_config)}"
            )

        models_dict = create_models_dict(apps_dict=apps_dict)
        apps_list: list = []
        for app_config in apps_config:
            app_markup: dict[str, str | list] | None = create_app_markup(
                app_config, apps_dict, models_dict
            )
            if app_markup is not None:
                apps_list.append(deepcopy(app_markup))
        if apps_list:
            self.apps_markup = apps_list
        return apps_list


def create_models_dict(apps_dict: dict[str | dict]) -> dict[str, dict]:
    models_dict = {}
    for app_name, app_info in apps_dict.items():
        model_info = {f"{app_name}.{model['object_name']}": model for model in app_info["models"]}
        models_dict.update(model_info)
    return models_dict


@functools.singledispatch
def create_app_markup(app_config, apps_dict, models_dict):
    raise TypeError(f"ADMIN_REORDER item must be dict or string. Got {type(app_config)}")


@create_app_markup.register
def _(
    app_config: str, apps_dict: dict[str | dict], models_dict: dict[str | dict]
) -> dict[str, str | list] | None:
    app_markup: dict[str, str | list] | None = apps_dict.get(app_config)
    if app_markup is None:
        return
    app_markup["models"].sort(key=lambda x: x["name"])
    return app_markup


@create_app_markup.register
def _(
    app_config: dict, apps_dict: dict[str | dict], models_dict: dict[str | dict]
) -> dict[str, str | list] | None:
    app_markup: dict[str, str | list] | None = apps_dict.get(app_config["app"])
    if app_markup is None:
        return
    app_markup["models"] = [
        models_dict[model_name] for model_name in app_config["models"] if model_name in models_dict
    ]
    if "label" in app_config:
        app_markup["name"] = app_config["label"]
    return app_markup
