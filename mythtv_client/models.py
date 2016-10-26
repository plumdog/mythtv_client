import collections
from enum import Enum

from vtypes import (
    VString,
    VInt,
    VBool,
    VUnsignedInt,
    VDict,
    VValidatorDict,
    VList,
    VDate,
    VDateTime,
    VTime,
    VEnum,
    Validator,
)


class Props(object):
    @classmethod
    def _attrs(cls):
        return [name for name in dir(cls) if not name.startswith('_') and name != 'decode']

    @classmethod
    def decode(cls, props):
        found = set()
        for name in cls._attrs():
            val = getattr(cls, name)
            formatted_name = name.split('_', 1)[1].lower()
            if props & val:
                found.add(formatted_name)
        return found


class RecordingType(Enum):
    """From https://github.com/MythTV/mythtv/blob/master/mythtv/libs/libmyth/recordingtypes.cpp#L76

    The `toRawString` method converts to a string. I believe this are
    always returned untranslated.

    """
    single_record = 'Single Record'
    all_record = 'Record All'
    record_one = 'Record One'
    record_daily = 'Record Daily'
    record_weekly = 'Record Weekly'
    override_recording = 'Override Recording'
    recording_template = 'Recording Template'
    not_recording = 'Not Recording'

    @property
    def is_on(self):
        return (self in self.__class__.on())

    @property
    def is_off(self):
        return (self in self.__class__.off())

    @classmethod
    def on(cls):
        return {
            cls.single_record,
            cls.all_record,
            cls.record_one,
            cls.record_daily,
            cls.record_weekly,
        }

    @classmethod
    def off(cls):
        return set(cls) - cls.on


class VideoProps(Props):
    VID_UNKNOWN = 0
    VID_HDTV = 1
    VID_WIDESCREEN = 2
    VID_AVC = 4
    VID_720 = 8
    VID_1080 = 16


class Base(object):
    attr_key = None
    attr_keys = []
    repr_attrs = []

    sort_attr = None

    def __getattr__(self, attr):
        for attr_key in self._get_attr_keys():
            obj = getattr(self, attr_key)
            if isinstance(obj, dict) and (attr in obj):
                return obj[attr]
            try:
                return getattr(obj, attr)
            except AttributeError:
                pass
        raise AttributeError('No such attribute {}'.format(attr))

    def __repr__(self):
        args = [' {}={}'.format(arg, getattr(self, arg)) for arg in self.repr_attrs]
        return '<{self.__class__.__name__}{args}>'.format(self=self, args=''.join(args))

    def __lt__(self, other):
        return getattr(self, self.sort_attr) < getattr(other, sort_attr)

    def _get_attr_keys(self):
        if self.attr_keys:
            return self.attr_keys
        if self.attr_key:
            return [self.attr_key]
        raise ValueError('Unable to get attr keys')

    def __init__(self, *args, **kwargs):
        attr_keys = self._get_attr_keys()
        found_num_args = (len(args) + len(kwargs))
        expected_num_args = len(attr_keys)
        if expected_num_args != found_num_args:
            raise TypeError('Unexpected num args. Found {}, expected {}.'.format(
                found_num_args, expected_num_args
            ))
        args_as_kwargs = {}
        for attr, arg in zip(attr_keys, args):
            args_as_kwargs[attr] = arg

        repeats = set(args_as_kwargs.keys()) & set(kwargs.keys())
        if repeats:
            raise TypeError('Repeated args and kwargs: {}'.format(repeats))

        for attr, value in args_as_kwargs.items():
            setattr(self, attr, value)

        for kw_attr, kw_value in kwargs.items():
            setattr(self, kw_attr, kw_value)


class Program(Base):
    attr_keys = ['_program', 'channel']
    repr_attrs = ['Title', 'StartTime', 'EndTime', 'ChannelName']
    validator = Validator(
        StartTime=VString(),
        VideoProps=VString(),
        Repeat=VString(),
        Artwork=VValidatorDict(
            validator=Validator(
                ArtworkInfos=VList())),
        Title=VString(),
        CatType=VString(),
        AudioProps=VString(),
        Category=VString(),
        SubProps=VString(),
        Recording=VValidatorDict(
            validator=Validator(
                RecordedId=VUnsignedInt(),
                Status=VString(),  # TODO: RecStatus.Type ???
                Priority=VInt(required=False),
                StartTs=VDateTime(required=False),
                EndTs=VDateTime(required=False),
                FileSize=VInt(required=False),
                FileName=VString(required=False),
                HostName=VString(required=False),
                LastModified=VDateTime(required=False),
                RecordId=VInt(required=False),
                RecGroup=VString(required=False),
                PlayGroup=VString(required=False),
                StorageGroup=VString(required=False),
                RecType=VInt(required=False),
                DupInType=VInt(required=False),
                DupMethod=VInt(required=False),
                EncoderId=VInt(required=False),
                EncoderName=VString(required=False),
                Profile=VString(required=False),
            )
        ),
        SubTitle=VString(),
        EndTime=VString(),
    )

    @property
    def video_props_list(self):
        return VideoProps.decode(int(self.VideoProps))


class Channel(Base):
    attr_key = '_channel'
    repr_attrs = ['ChanNum', 'ChannelName']
    validator = Validator(
        ChannelName=VString(),
        ChanId=VString(),
        CallSign=VString(),
        IconURL=VString(),
        ChanNum=VString(),
        Programs=VList(of=VValidatorDict(validator=Program.validator)),
    )

    @property
    def programs(self):
        for pr_dict in self._channel['Programs']:
            yield Program(pr_dict, self)


class ProgramGuide(Base):
    attr_key = '_guide'
    repr_attrs = ['StartTime', 'EndTime']

    args = {
        '_guide': Validator(
            AsOf=VString(),
            EndTime=VString(),
            ProtoVer=VString(),
            StartTime=VString(),
            StartIndex=VString(),
            Version=VString(),
            TotalAvailable=VString(),
            Count=VString(),
            Channels=VList(of=VValidatorDict(validator=Channel.validator)),
            # Channels=VList(of=VDict()),
            Details=VString(),
        ),
    }

    @property
    def channels(self):
        for ch_dict in self._guide['Channels']:
            yield Channel(ch_dict)

    @property
    def programs(self):
        for ch in self.channels:
            yield from ch.programs

    def search(self, term, remove_dups=True, limit=None):
        matches = []
        for pr in self.programs:
            if term.lower() in pr.Title.lower():
                matches.append(pr)

        if remove_dups:
            keyed = collections.defaultdict(list)

            def _pick_best(dups):
                hd = []
                ordered = sorted(dups, key=lambda pr: int(pr.channel.ChanNum))
                for pr in ordered:
                    if 'hdtv' in pr.video_props_list:
                        return pr
                return ordered[0]

            for pr in matches:
                key = (pr.Title, pr.StartTime, pr.EndTime)
                keyed[key].append(pr)

            deduped = []
            for ch_pr_lists in keyed.values():
                deduped.append(_pick_best(ch_pr_lists))
            matches = deduped

        found = sorted(matches, key=lambda pr: pr.StartTime)
        if limit:
            found = found[:limit]
        return found


class RecRule(Base):
    attr_keys = ['_recrule']
    repr_attrs = ['StartTime', 'Title']
    validator = Validator(
        Id=VInt(),
        ParentId=VInt(),
        Inactive=VBool(),
        Title=VString(),
        SubTitle=VString(),
        Description=VString(),
        Season=VUnsignedInt(),
        Episode=VUnsignedInt(),
        Category=VString(),
        StartTime=VDateTime(required=False),
        EndTime=VDateTime(required=False),
        SeriesId=VString(),
        ProgramId=VString(),
        Inetref=VString(),
        ChanId=VInt(),
        CallSign=VString(),
        FindDay=VInt(),
        FindTime=VTime(required=False),
        Type=VEnum(enum=RecordingType),
        SearchType=VString(),
        RecPriority=VInt(),
        PreferredInput=VUnsignedInt(),
        StartOffset=VInt(),
        EndOffset=VInt(),
        DupMethod=VString(),
        DupIn=VString(),
        Filter=VUnsignedInt(),
        RecProfile=VString(),
        RecGroup=VString(),
        StorageGroup=VString(),
        PlayGroup=VString(),
        AutoExpire=VBool(),
        MaxEpisodes=VInt(),
        MaxNewest=VBool(),
        AutoCommflag=VBool(),
        AutoTranscode=VBool(),
        AutoMetaLookup=VBool(),
        AutoUserJob1=VBool(),
        AutoUserJob2=VBool(),
        AutoUserJob3=VBool(),
        AutoUserJob4=VBool(),
        Transcoder=VInt(),
        NextRecording=VDateTime(required=False),
        LastRecorded=VDateTime(required=False),
        LastDeleted=VDateTime(required=False),
        AverageDelay=VInt(),
    )
    args = {
        '_recrule': validator
    }


class RecRuleList(Base):
    attr_key = '_recrulelist'
    repr_attrs = ['AsOf', 'StartIndex', 'Count']
    validator = Validator(
        StartIndex=VInt(),
        Count=VInt(),
        TotalAvailable=VInt(),
        AsOf=VDateTime(required=False),
        Version=VString(),
        ProtoVer=VString(),
        RecRules=VList(of=VValidatorDict(validator=RecRule.validator)),
    )

    @property
    def all_rec_rules(self):
        yield from (RecRule(rr) for rr in self.RecRules)

    @property
    def non_template_rec_rules(self):
        yield from (rr for rr in self.all_rec_rules if rr.Type.is_on)

    def __iter__(self):
        return iter(self.non_template_rec_rules)
