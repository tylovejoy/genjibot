from __future__ import annotations

import enum
from typing import Generic, TypeVar, TYPE_CHECKING, Any, Iterable

import discord
from discord import app_commands


if TYPE_CHECKING:
    import database


class DoesNotExist(Exception):
    """Cache object cannot be removed as it does not exist."""


class AlreadyExists(Exception):
    """Cache object cannot be added as it already exists."""


class SettingFlags(enum.IntFlag):
    VERIFICATION = enum.auto()
    PROMOTION = enum.auto()
    DEFAULT = VERIFICATION | PROMOTION
    NONE = 0

    def get_new_flag(self, value: int):
        return self.value ^ value


class Cache:
    def __init__(self):
        self.refresh()

    def refresh(self) -> None:
        raise NotImplementedError


T = TypeVar("T", bound=Cache)


class StrCache(Cache):
    def __init__(self, value: str):
        self.value = value
        super().__init__()


class ChoiceMixin:
    choice: app_commands.Choice[str] | None = None

    def _update_choice(self, *, name: str, value: str) -> None:
        if not self.choice:
            self.choice = app_commands.Choice(name=name, value=value)
        else:
            self.choice.name = name
            self.choice.value = value


class OptionMixin:
    option: discord.SelectOption | None = None

    def _update_option(self, *, label: str, value: str) -> None:
        if not self.option:
            self.option = discord.SelectOption(label=label, value=value)
        else:
            self.option.label = label
            self.option.value = value


class ChoiceOptionStrCache(StrCache, ChoiceMixin, OptionMixin):
    def __init__(self, value: str):
        super().__init__(value)

    def refresh(self) -> None:
        self._update_choice(name=self.value, value=self.value)
        self._update_option(label=self.value, value=self.value)


class MapNamesData(ChoiceOptionStrCache):
    ...


class MapTypesData(ChoiceOptionStrCache):
    ...


class MapMechanicsData(ChoiceOptionStrCache):
    ...


class MapRestrictionsData(ChoiceOptionStrCache):
    ...


class TagsData(ChoiceOptionStrCache):
    ...


class MapData(Cache, ChoiceMixin):
    def __init__(self, map_code: str, user_ids: set[int], archived: bool):
        self.map_code = map_code
        self.user_ids = user_ids
        self.archived = archived
        super().__init__()

    def refresh(self):
        self._update_choice(name=self.map_code, value=self.map_code)

    def update_map_code(self, map_code: str):
        self.map_code = map_code
        self.refresh()

    def add_creator(self, user_id: int):
        if user_id in self.user_ids:
            raise AlreadyExists
        self.user_ids.add(user_id)

    def remove_creator(self, user_id: int):
        if user_id not in self.user_ids:
            raise DoesNotExist
        self.user_ids.remove(user_id)

    def update_archived(self, value: bool):
        self.archived = value


class UserData(Cache, ChoiceMixin):
    def __init__(
        self, user_id: int, nickname: str, flags: SettingFlags, is_creator: bool
    ):
        self.user_id = user_id
        self.nickname = nickname
        self.flags = flags
        self.is_creator = is_creator
        super().__init__()

    def refresh(self):
        self._update_choice(name=self.nickname, value=str(self.user_id))

    def update_nickname(self, nickname: str):
        self.nickname = nickname
        self.refresh()

    def update_user_id(self, user_id: int):
        self.user_id = user_id
        self.refresh()

    def update_flag(self, flag: SettingFlags):
        self.flags = self.flags.get_new_flag(flag.value)

    def update_is_creator(self, value: bool):
        self.is_creator = value


class SequenceCache(Generic[T]):
    def __init__(self, key_value: str):
        self.key_value = key_value
        self.values: list[T] = []

    def __getitem__(self, item: int):
        return self.find(item)

    def __iter__(self) -> Iterable[T]:
        return iter(self.values)

    @property
    def keys(self) -> list[str | int]:
        return [getattr(x, self.key_value) for x in self.values]

    @property
    def choices(self):
        return self._choices(self.values)

    @staticmethod
    def _choices(iterable: list[T]) -> list[app_commands.Choice[str]]:
        return [x.choice for x in iterable]

    def create_obj(self, *args: Any, **kwargs: Any):
        return self.__class__(*args, **kwargs)

    def add_one(self, obj: T):
        if getattr(obj, self.key_value) in self.values:
            raise AlreadyExists
        self.add_many([obj])

    def add_many(self, objs: list[T]):
        _objs: list[T] = []
        for obj in objs:
            if getattr(obj, self.key_value) in self.keys:
                raise AlreadyExists
            _objs.append(obj)
        self.values.extend(_objs)

    def remove_one(self, key: str | int):
        if key not in self.keys:
            raise DoesNotExist
        found = self.find(key)
        if found:
            self.values.remove(found)

    def clear_all(self):
        self.values = []

    def find(self, key: int | str) -> T:
        return self._find_one(self.values, self.key_value, key)

    @staticmethod
    def _find_one(cls_var: list[T], key: str, value: Any) -> T:
        for obj in cls_var:
            if getattr(obj, key) == value:
                return obj

    @staticmethod
    def _find_many(cls_var: list[T], key: str, value: Any) -> list[T]:
        res: list[T] = []
        for obj in cls_var:
            if getattr(obj, key) == value:
                res.append(obj)
        return res


class Users(SequenceCache[T]):
    def __init__(self):
        self.key_value = "user_id"
        super().__init__(self.key_value)

    @property
    def creator_choices(self) -> list[app_commands.Choice[str]]:
        return self._choices(self._find_many(self.values, "is_creator", True))

    @property
    def creator_ids(self) -> list[int]:
        return [x.user_id for x in self._find_many(self.values, "is_creator", True)]


class Maps(SequenceCache[T]):
    def __init__(self):
        self.key_value = "map_code"
        super().__init__(self.key_value)

    def __getitem__(self, item: str):
        return self.find(item)


class StrCacheSequence(SequenceCache[T]):
    def __init__(self):
        self.key_value = "value"
        super().__init__(self.key_value)

    @property
    def options(self) -> list[discord.SelectOption]:
        return [x.option for x in self.values]

    @property
    def list(self) -> list[str]:
        return [x.value for x in self.values]

    def __iter__(self) -> Iterable[str]:
        return iter(self.list)


class MapTypes(StrCacheSequence[T]):
    ...


class MapNames(StrCacheSequence[T]):
    ...


class MapRestrictions(StrCacheSequence[T]):
    ...


class MapMechanics(StrCacheSequence[T]):
    ...


class Tags(StrCacheSequence[T]):
    ...


class GenjiCache:
    def __init__(self):
        self.users: Users[UserData] = Users()
        self.maps: Maps[MapData] = Maps()
        self.map_names: MapNames[MapNamesData] = MapNames()
        self.map_types: MapTypes[MapTypesData] = MapTypes()
        self.map_mechanics: MapMechanics[MapMechanicsData] = MapMechanics()
        self.map_restrictions: MapRestrictions[MapMechanicsData] = MapRestrictions()
        self.tags: Tags[TagsData] = Tags()

    def setup(
        self,
        *,
        users: list[database.DotRecord | None],
        maps: list[database.DotRecord | None],
        map_names: list[database.DotRecord | None],
        map_types: list[database.DotRecord | None],
        map_mechanics: list[database.DotRecord | None],
        map_restrictions: list[database.DotRecord | None],
        tags: list[database.DotRecord | None],
    ):
        self.add_users(users)
        self.add_maps(maps)
        self.add_map_names(map_names)
        self.add_map_types(map_types)
        self.add_map_mechanics(map_mechanics)
        self.add_map_restrictions(map_restrictions)
        self.add_tags(tags)

    def refresh_cache(self):
        self._refresh(self.users)
        self._refresh(self.maps)
        self._refresh(self.map_names)
        self._refresh(self.map_types)
        self._refresh(self.map_mechanics)
        self._refresh(self.map_restrictions)
        self._refresh(self.tags)

    @staticmethod
    def _refresh(cls_var: list[T]):
        for x in cls_var:
            x.refresh()

    def add_users(self, users: list[database.DotRecord]):
        _users = [
            UserData(
                user_id=x.user_id,
                nickname=x.nickname,
                flags=SettingFlags(x.flags),
                is_creator=x.is_creator,
            )
            for x in users
        ]
        self.users.add_many(_users)

    def add_maps(self, maps: list[database.DotRecord]):
        _maps = [
            MapData(
                map_code=x.map_code,
                user_ids=x.user_ids,
                archived=x.archived,
            )
            for x in maps
        ]
        self.maps.add_many(_maps)

    def add_map_names(self, map_names: list[database.DotRecord]):
        _map_names = [
            MapNamesData(
                value=x.value,
            )
            for x in map_names
        ]
        self.map_names.add_many(_map_names)

    def add_map_types(self, map_types: list[database.DotRecord]):
        _map_types = [
            MapTypesData(
                value=x.value,
            )
            for x in map_types
        ]
        self.map_types.add_many(_map_types)

    def add_map_mechanics(self, map_mechanics: list[database.DotRecord]):
        _map_mechanics = [
            MapMechanicsData(
                value=x.value,
            )
            for x in map_mechanics
        ]
        self.map_mechanics.add_many(_map_mechanics)

    def add_map_restrictions(self, map_restrictions: list[database.DotRecord]):
        _map_restrictions = [
            MapRestrictionsData(
                value=x.value,
            )
            for x in map_restrictions
        ]
        self.map_restrictions.add_many(_map_restrictions)

    def add_tags(self, tags: list[database.DotRecord]):
        _tags = [
            MapRestrictionsData(
                value=x.value,
            )
            for x in tags
        ]
        self.tags.add_many(_tags)
