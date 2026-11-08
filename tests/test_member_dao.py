import pytest

from dao.errors import DAOError, ErrorCode
from dao.member_dao import MemberDAO


@pytest.mark.integration
def test_search_and_get(clerk_conn):
    dao = MemberDAO()
    page = dao.search(clerk_conn)
    assert page.total == 2
    assert [item["member_id"] for item in page.items] == ["M001", "M002"]

    member = dao.get(clerk_conn, "M001")
    assert member is not None
    assert dao.search(clerk_conn, keyword="M001").total == 1
    assert dao.search(clerk_conn, keyword=member["phone"]).total == 1
    assert dao.search(clerk_conn, keyword="' OR 1=1 --").total == 0
    assert dao.get(clerk_conn, "M999") is None


@pytest.mark.integration
def test_create_member(clerk_conn):
    dao = MemberDAO()
    member = dao.create(
        clerk_conn,
        member_name="测试会员",
        phone="13700009999",
        points=10,
    )
    assert member["member_id"].startswith("M")
    assert len(member["member_id"]) == 8
    assert member["points"] == 10
    assert dao.get(clerk_conn, member["member_id"]) == member


@pytest.mark.integration
def test_duplicate_phone_conflicts(clerk_conn):
    existing = MemberDAO().get(clerk_conn, "M001")
    assert existing is not None
    with pytest.raises(DAOError) as excinfo:
        MemberDAO().create(
            clerk_conn,
            member_name="重复手机号",
            phone=existing["phone"],
        )
    assert excinfo.value.code == ErrorCode.CONFLICT_UNIQUE


@pytest.mark.integration
def test_update_member(clerk_conn):
    dao = MemberDAO()
    updated = dao.update(clerk_conn, "M002", {"member_name": "测试改名", "points": 60})
    assert updated is not None
    assert updated["member_name"] == "测试改名"
    assert updated["points"] == 60

    with pytest.raises(DAOError) as excinfo:
        dao.update(clerk_conn, "M002", {"member_id": "M999"})
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR

    assert dao.update(clerk_conn, "M999", {"points": 1}) is None


@pytest.mark.integration
def test_add_points(clerk_conn):
    dao = MemberDAO()
    added = dao.add_points(clerk_conn, "M002", 25)
    assert added is not None and added["points"] == 75

    deducted = dao.add_points(clerk_conn, "M002", -15)
    assert deducted is not None and deducted["points"] == 60

    assert dao.add_points(clerk_conn, "M999", 1) is None


@pytest.mark.integration
def test_add_points_rejects_negative_balance(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        MemberDAO().add_points(clerk_conn, "M002", -51)
    error = excinfo.value
    assert error.code == ErrorCode.BUSINESS_RULE_VIOLATION
    assert error.context == {"member_id": "M002", "available": 50, "requested": 51}


@pytest.mark.integration
def test_create_rejects_negative_points(clerk_conn):
    with pytest.raises(DAOError) as excinfo:
        MemberDAO().create(clerk_conn, member_name="负积分", phone="13700008888", points=-1)
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
