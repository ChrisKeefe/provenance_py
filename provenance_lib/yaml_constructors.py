import warnings

from typing import List, TypedDict, Union

# Alias string as UUID so we can specify types more clearly
UUID = str


def color_constructor(loader, node) -> str:
    """
    Constructor for !color tags.
    TODO: What even are these things? They don't appear to be used in qiime2.
    This will probably need to be rewritten from a simple string rendering
    """
    return loader.construct_scalar(node)


def citation_key_constructor(loader, node) -> str:
    """
    A constructor for !cite yaml tags, returning a bibtex key as a str.
    All we need for now is a key string we can match in citations.bib,
    so _we're not parsing these into component substrings_.

    If that need arises in future, these are spec'ed in provenance.py as:
    <domain>|<package>:<version>|[<identifier>|]<index>

    and frequently look like this (note no identifier):
    framework|qiime2:2020.6.0.dev0|0
    """
    value = loader.construct_scalar(node)
    return value


class MetadataInfo(TypedDict):
    """ A static type def for metadata_path_constructor's return value """
    input_artifact_uuids: List[UUID]
    relative_fp: str


def metadata_path_constructor(loader, node) -> MetadataInfo:
    """
    A constructor for !metadata yaml tags, which come in the form
    [<uuid_ref>[,<uuid_ref>][...]:]<relative_filepath>

    Most commonly, we see:
    !metadata 'sample_metadata.tsv'

    In cases where Artifacts are used as metadata, we see:
    !metadata '415409a4-371d-4c69-9433-e3eaba5301b4:feature_metadata.tsv'

    In cases where multiple Artifacts as metadata were merged,
    it is possible for multiple comma-separated uuids to precede the ':'
    !metadata '<uuid1>,<uuid2>,...,<uuidn>:feature_metadata.tsv'

    The metadata files (including "Artifact metadata") are saved in the same
    dir as `action.yaml`. The UUIDs listed must be incorporated into our
    provenance graph as parents, so are returned in list form.
    """
    # TODO: add Artifact "metadata" to provenance as inputs/parents
    raw = loader.construct_scalar(node)
    if ':' in raw:
        artifact_uuids, rel_fp = raw.split(':')
        artifact_uuids = artifact_uuids.split(',')
    else:
        artifact_uuids = []
        rel_fp = raw
    return {'input_artifact_uuids': artifact_uuids, 'relative_fp': rel_fp}


def no_provenance_constructor(loader, node) -> MetadataInfo:
    """
    Constructor for !no-provenance tags. These tags are produced when an input
    has no /provenance dir, as is the case with v0 archives that have been
    used in analyses in QIIME2 V1+. They look like this:

    action:
       inputs:
       -   table: !no-provenance '34b07e56-27a5-4f03-ae57-ff427b50aaa1'

    TODO: Is this the right place to warn? Is there anything else we need to do
    with this information downstream? E.g. add an attribute to this node
    indicating it is problematic, so it can be colored when drawing?
    """
    uuid = loader.construct_scalar(node)
    warnings.warn(f"Artifact {uuid} was created prior to provenance tracking. "
                  + "Provenance data will be incomplete.", UserWarning)
    return uuid


def ref_constructor(loader, node) -> Union[str, List[str]]:
    """
    A constructor for !ref yaml tags. These tags describe yaml values that
    reference other namespaces within the document, using colons to separate
    namespaces. For example:
    !ref 'environment:plugins:sample-classifier'

    At present, ForwardRef tags are only used in the framework to 'link' the
    plugin name to the plugin version and other details in the 'execution'
    namespace of action.yaml

    This constructor explicitly handles this type of !ref by extracting and
    returning the plugin name to simplify parsing, while supporting the return
    of a generic list of 'keys' (e.g. ['environment', 'framework', 'version'])
    in the event ForwardRef is used more broadly in future.
    """
    value = loader.construct_scalar(node)
    keys = value.split(':')
    if keys[0:2] == ['environment', 'plugins']:
        plugin_name = keys[2]
        return plugin_name
    else:
        return keys


def set_constructor(loader, node) -> str:
    """
    A constructor for !set yaml tags, returning a python set object
    """
    value = loader.construct_sequence(node)
    return set(value)