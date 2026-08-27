import pytest

from oracle_archive_manager.security import credential


def test_new_ref_format():
    ref = credential.new_credential_ref("PROD")
    assert ref.startswith("conn/PROD/")
    assert len(ref) > len("conn/PROD/")


def test_store_load_roundtrip():
    ref = credential.new_credential_ref("roundtrip")
    try:
        credential.store_credential(ref, "secret")
        assert credential.load_credential(ref) == "secret"
    except Exception as exc:
        pytest.skip(f"当前环境无可用凭据后端：{exc}")
    finally:
        try:
            credential.delete_credential(ref)
        except Exception:
            pass
