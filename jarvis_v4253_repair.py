"""Release identity for reliable attachment intake; existing repair gates retained."""
import re
import sys

VERSION = '42.53.2'


def install(g):
    previous = g['_v36_release_identity']
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-2])_repair', name):
            module.VERSION = VERSION

    def identity():
        result = dict(previous())
        result.update(version='V' + VERSION, project_zip_chunked_uploads=True,
                      project_zip_handoff_requires_ack=True,
                      missing_attachment_cannot_start_generation=True,
                      language_framework_toolchain_agnostic=True)
        return result

    g.update(_v36_release_identity=identity, V4253_VERSION=VERSION)
