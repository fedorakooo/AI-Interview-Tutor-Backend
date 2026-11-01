from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler


def test_invitation_token_is_opaque_and_only_its_peppered_hash_is_comparable():
    handler = InvitationTokenHandler("test-pepper")
    token = handler.generate()
    token_hash = handler.hash(token)

    assert len(token) >= 43
    assert token not in token_hash
    assert handler.matches(token, token_hash)
    assert not handler.matches(handler.generate(), token_hash)
