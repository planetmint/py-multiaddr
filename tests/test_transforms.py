import io

import pytest

from multiaddr.codecs import codec_by_name

from multiaddr.exceptions import StringParseError
from multiaddr.exceptions import BinaryParseError

from multiaddr.transforms import bytes_iter
from multiaddr.transforms import bytes_to_string
from multiaddr.transforms import size_for_addr
from multiaddr.transforms import string_to_bytes

import multiaddr.protocols
from multiaddr.protocols import REGISTRY
from multiaddr.protocols import Protocol

# These test values were generated by running them through the go implementation
# of multiaddr (https://github.com/multiformats/go-multiaddr)
#
# All values are bijective.
ADDR_BYTES_STR_TEST_DATA = [
    (REGISTRY.find("ip4"), b"\x0a\x0b\x0c\x0d", "10.11.12.13"),
    (
        REGISTRY.find("ip6"),
        b"\x1a\xa1\x2b\xb2\x3c\xc3\x4d\xd4\x5e\xe5\x6f\xf6\x7a\xb7\x8a\xc8",
        "1aa1:2bb2:3cc3:4dd4:5ee5:6ff6:7ab7:8ac8",
    ),
    (REGISTRY.find("tcp"), b"\xab\xcd", "43981"),
    (REGISTRY.find("onion"), b"\x9a\x18\x08\x73\x06\x36\x90\x43\x09\x1f\x04\xd2", "timaq4ygg2iegci7:1234"),
    (
        REGISTRY.find("p2p"),
        b"\x01\x72\x12\x20\xd5\x2e\xbb\x89\xd8\x5b\x02\xa2\x84\x94\x82\x03\xa6\x2f"
        b"\xf2\x83\x89\xc5\x7c\x9f\x42\xbe\xec\x4e\xc2\x0d\xb7\x6a\x68\x91\x1c\x0b",
        "QmcgpsyWgH8Y8ajJz1Cu72KnS5uo2Aa2LpzU7kinSupNKC",
    ),
    # Additional test data
    (
        REGISTRY.find("dns4"),
        b"\xd9\x85\xd9\x88\xd9\x82\xd8\xb9.\xd9\x88\xd8\xb2\xd8\xa7\xd8\xb1\xd8\xa9"
        b"-\xd8\xa7\xd9\x84\xd8\xa7\xd8\xaa\xd8\xb5\xd8\xa7\xd9\x84\xd8\xa7\xd8\xaa"
        b".\xd9\x85\xd8\xb5\xd8\xb1",
        # Explicitly mark this as unicode, as the “u” forces the text to be displayed LTR in editors
        "موقع.وزارة-الاتصالات.مصر",
    ),
    (
        REGISTRY.find("dns4"),
        b"fu\xc3\x9fball.example",
        "fußball.example",
    ),  # This will fail if IDNA-2003/NamePrep is used
]

ADDR_BYTES_FROM_STR_TEST_DATA = [
    # New CIDv1 string to new CIDv1 binary format mapping (non-bijective)
    (
        REGISTRY.find("p2p"),
        b"\x01\x72\x12\x20\xd5\x2e\xbb\x89\xd8\x5b\x02\xa2\x84\x94\x82\x03\xa6\x2f"
        b"\xf2\x83\x89\xc5\x7c\x9f\x42\xbe\xec\x4e\xc2\x0d\xb7\x6a\x68\x91\x1c\x0b",
        "bafzbeigvf25ytwc3akrijfecaotc74udrhcxzh2cx3we5qqnw5vgrei4bm",
    ),
]

ADDR_BYTES_TO_STR_TEST_DATA = [
    # Old CIDv0 binary to old CIDv0 string format mapping (non-bijective)
    (
        REGISTRY.find("p2p"),
        b"\x12\x20\xd5\x2e\xbb\x89\xd8\x5b\x02\xa2\x84\x94\x82\x03\xa6\x2f\xf2"
        b"\x83\x89\xc5\x7c\x9f\x42\xbe\xec\x4e\xc2\x0d\xb7\x6a\x68\x91\x1c\x0b",
        "QmcgpsyWgH8Y8ajJz1Cu72KnS5uo2Aa2LpzU7kinSupNKC",
    ),
]

BYTES_MAP_STR_TEST_DATA = [
    ("/ip4/127.0.0.1/udp/1234", b"\x04\x7f\x00\x00\x01\x91\x02\x04\xd2"),
    ("/ip4/127.0.0.1/tcp/4321", b"\x04\x7f\x00\x00\x01\x06\x10\xe1"),
    (
        "/ip4/127.0.0.1/udp/1234/ip4/127.0.0.1/tcp/4321",
        b"\x04\x7f\x00\x00\x01\x91\x02\x04\xd2\x04\x7f\x00\x00\x01\x06\x10\xe1",
    ),
]


@pytest.mark.parametrize(
    "codec_name, buf, expected",
    [
        (None, b"\x01\x02\x03", (0, 0)),
        ("ip4", b"\x01\x02\x03", (4, 0)),
        ("cid", b"\x40\x50\x60\x51", (64, 1)),
    ],
)
def test_size_for_addr(codec_name, buf, expected):
    buf_io = io.BytesIO(buf)
    assert (size_for_addr(codec_by_name(codec_name), buf_io), buf_io.tell()) == expected


@pytest.mark.parametrize(
    "buf, expected",
    [
        # "/ip4/127.0.0.1/udp/1234/ip4/127.0.0.1/tcp/4321"
        (
            b"\x04\x7f\x00\x00\x01\x91\x02\x04\xd2\x04\x7f\x00\x00\x01\x06\x10\xe1",
            [
                (REGISTRY.find("ip4"), b"\x7f\x00\x00\x01"),
                (REGISTRY.find("udp"), b"\x04\xd2"),
                (REGISTRY.find("ip4"), b"\x7f\x00\x00\x01"),
                (REGISTRY.find("tcp"), b"\x10\xe1"),
            ],
        ),
    ],
)
def test_bytes_iter(buf, expected):
    assert list((proto, val) for _, proto, _, val in bytes_iter(buf)) == expected


@pytest.mark.parametrize("proto, buf, expected", ADDR_BYTES_STR_TEST_DATA + ADDR_BYTES_TO_STR_TEST_DATA)
def test_codec_to_string(proto, buf, expected):
    assert codec_by_name(proto.codec).to_string(proto, buf) == expected


@pytest.mark.parametrize("proto, expected, string", ADDR_BYTES_STR_TEST_DATA + ADDR_BYTES_FROM_STR_TEST_DATA)
def test_codec_to_bytes(proto, string, expected):
    assert codec_by_name(proto.codec).to_bytes(proto, string) == expected


@pytest.mark.parametrize("string, buf", BYTES_MAP_STR_TEST_DATA)
def test_string_to_bytes(string, buf):
    assert string_to_bytes(string) == buf


@pytest.mark.parametrize("string, buf", BYTES_MAP_STR_TEST_DATA)
def test_bytes_to_string(string, buf):
    assert bytes_to_string(buf) == string


class DummyProtocol(Protocol):
    def __init__(self, code, name, codec=None):
        self.code = code
        self.name = name
        self.codec = codec


class UnparsableProtocol(DummyProtocol):
    def __init__(self):
        super().__init__(333, "unparsable", "?")


@pytest.fixture
def protocol_extension(monkeypatch):
    # “Add” additional non-parsable protocol to protocols from code list
    registry = multiaddr.protocols.REGISTRY.copy(unlock=True)
    registry.add(UnparsableProtocol())
    monkeypatch.setattr(multiaddr.protocols, "REGISTRY", registry)


@pytest.mark.parametrize("string", ["test", "/ip4/", "/unparsable/5"])
def test_string_to_bytes_value_error(protocol_extension, string):
    with pytest.raises(StringParseError):
        string_to_bytes(string)


@pytest.mark.parametrize("bytes", [b"\xcd\x02\x0c\x0d", b"\x35\x03a:b"])
def test_bytes_to_string_value_error(protocol_extension, bytes):
    with pytest.raises(BinaryParseError):
        bytes_to_string(bytes)


@pytest.mark.parametrize(
    "proto, address",
    [
        (REGISTRY.find("ip4"), "1124.2.3"),
        (REGISTRY.find("ip6"), "123.123.123.123"),
        (REGISTRY.find("tcp"), "a"),
        (REGISTRY.find("tcp"), "100000"),
        (REGISTRY.find("onion"), "100000"),
        (REGISTRY.find("onion"), "1234567890123456:0"),
        (REGISTRY.find("onion"), "timaq4ygg2iegci7:a"),
        (REGISTRY.find("onion"), "timaq4ygg2iegci7:0"),
        (REGISTRY.find("onion"), "timaq4ygg2iegci7:71234"),
        (REGISTRY.find("p2p"), "15230d52ebb89d85b02a284948203a"),
        (
            REGISTRY.find("p2p"),  # CID type != "libp2p-key":
            "bafyaajaiaejcbrrv5vds2whn3c464rsb5r2vpxeanneinzlijenlac77cju2pptf",
        ),
        (REGISTRY.find("ip6zone"), ""),
    ],
)
def test_codec_to_bytes_value_error(proto, address):
    # Codecs themselves may raise any exception type – it will then be converted
    # to `StringParseError` by a higher level
    with pytest.raises(Exception):
        codec_by_name(proto.codec).to_bytes(proto, address)


@pytest.mark.parametrize(
    "proto, buf",
    [
        (REGISTRY.find("tcp"), b"\xff\xff\xff\xff"),
        (
            REGISTRY.find("p2p"),  # CID type != "libp2p-key":
            b"\x01\x70\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41"
            b"\xec\x75\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
        ),
        (REGISTRY.find("ip6zone"), b""),
    ],
)
def test_codec_to_string_value_error(proto, buf):
    # Codecs themselves may raise any exception type – it will then be converted
    # to `BinaryParseError` by a higher level
    with pytest.raises(Exception):
        codec_by_name(proto.codec).to_string(proto, buf)


@pytest.mark.parametrize(
    "proto, string, expected",
    [
        (
            REGISTRY.find("p2p"),  # This one gets autoconverted to CIDv1
            "12D3KooWPA6ax6t3jqTyGq73Zm1RmwppYqxaXzrtarfcTWGp5Wzx",
            b"\x01\x72\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41"
            b"\xec\x75\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
        ),
        (
            REGISTRY.find("ip6"),  # Others do not
            "12D3KooWPA6ax6t3jqTyGq73Zm1RmwppYqxaXzrtarfcTWGp5Wzx",
            b"\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41\xec\x75"
            b"\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
        ),
    ],
)
def test_cid_autoconvert_to_bytes(proto, string, expected):
    assert codec_by_name("cid").to_bytes(proto, string) == expected


@pytest.mark.parametrize(
    "proto, buf, expected",
    [
        (
            REGISTRY.find("p2p"),  # This one gets autoconverted to CIDv0
            b"\x01\x72\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41"
            b"\xec\x75\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
            "12D3KooWPA6ax6t3jqTyGq73Zm1RmwppYqxaXzrtarfcTWGp5Wzx",
        ),
        (
            REGISTRY.find("ip6"),  # Others do not
            b"\x01\x72\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41"
            b"\xec\x75\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
            "bafzaajaiaejcbrrv5vds2whn3c464rsb5r2vpxeanneinzlijenlac77cju2pptf",
        ),
        (
            REGISTRY.find("ip6"),  # (Needed to put identity conversion test somewhere)
            b"\x00\x24\x08\x01\x12\x20\xc6\x35\xed\x47\x2d\x58\xed\xd8\xb9\xee\x46\x41\xec\x75"
            b"\x57\xdc\x80\x6b\x48\x86\xe5\x68\x49\x1a\xb0\x0b\xff\x12\x69\xa7\xbe\x65",
            "12D3KooWPA6ax6t3jqTyGq73Zm1RmwppYqxaXzrtarfcTWGp5Wzx",
        ),
    ],
)
def test_cid_autoconvert_to_string(proto, buf, expected):
    assert codec_by_name("cid").to_string(proto, buf) == expected
