from verifier import verify_fix


def test_compilation_verification_does_not_execute_candidate():
    result = verify_fix("raise RuntimeError('do not run')\n", [])
    assert result["compilation"]["passed"] is True
    assert result["candidate_executed"] is False
    assert result["status"] == "incomplete"


def test_compilation_failure_is_reported():
    result = verify_fix("if True\n    pass\n")
    assert result["compilation"]["ran"] is True
    assert result["compilation"]["passed"] is False
    assert result["status"] == "failed"


def test_trusted_fixture_expected_actual_pass():
    tests = [
        {
            "name": "sum",
            "operation": "sum_numbers",
            "input": [1, 2],
            "expected": 3,
        }
    ]
    result = verify_fix("total = 3\n", tests)
    assert result["trusted_tests"][0]["passed"] is True
    assert result["trusted_tests"][0]["actual"] == 3
    assert result["status"] == "sample_checks_passed"


def test_trusted_fixture_failure_is_not_hidden():
    tests = [
        {
            "name": "sum",
            "operation": "sum_numbers",
            "input": [1, 2],
            "expected": 999,
        }
    ]
    result = verify_fix("total = 2\n", tests)
    assert result["trusted_tests"][0]["passed"] is False
    assert result["trusted_tests"][0]["actual"] == 3
    assert result["status"] == "failed"


def test_untrusted_or_unknown_test_operation_fails_clearly():
    result = verify_fix(
        "total = 2\n",
        [{"name": "unknown", "operation": "user_code", "input": None, "expected": 2}],
    )
    assert result["trusted_tests"][0]["passed"] is False
    assert "Unsupported operation" in result["trusted_tests"][0]["detail"]


def test_reference_checks_do_not_execute_candidate():
    result = verify_fix(
        "raise RuntimeError('candidate must not run')\n",
        [{"name": "sum", "operation": "sum_numbers", "input": [1, 2], "expected": 3}],
    )
    assert result["candidate_executed"] is False
    assert result["trusted_tests"][0]["actual"] == 3
    assert result["trusted_tests"][0]["passed"] is True


def test_no_candidate_is_unavailable():
    assert verify_fix(None)["status"] == "not_available"
