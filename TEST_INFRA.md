# E2E Test Infrastructure & Coverage Documentation

## 1. Overview & Testing Philosophy

The BauntyCinemBot E2E Test Suite provides complete, opaque-box, contract-driven verification across all 5 primary user requirements (R1–R5) and all 27 features in `PROJECT.md § Feature Inventory`.

### Testing Principles
1. **Opaque-Box Specification Verification**: Tests interact strictly through public interfaces, HTTP endpoints, middleware contracts, and database CRUD boundaries without coupling to internal private implementations.
2. **Deterministic & Isolated Execution**: Every test sets up its own isolated state (in-memory SQLite session, clean security service state, mock external Telegram/remote network gateways) and cleans up automatically.
3. **Progressive Testability & Defect Escalation**: Tests verify contracts defined in `PROJECT.md`. When implementation defects or unhandled race conditions are encountered, they are escalated to the relevant milestone worker rather than masking logic in tests.
4. **Adversarial Resilience**: Every feature is hardened against edge cases, boundary parameters, malformed headers, and injection payloads.

---

## 2. 4-Tier Test Architecture

The E2E suite is partitioned into four explicit, verifiable tiers:

```
tests/e2e/
├── __init__.py
├── conftest.py                       # Shared async fixtures (in-memory DB, WebApp client, mocks)
├── test_tier1_feature_coverage.py    # Tier 1: Direct feature coverage (>=5 tests per feature, 135 tests)
├── test_tier2_boundary_corner.py     # Tier 2: Boundary & corner cases (>=5 tests per feature, 135 tests)
├── test_tier3_cross_feature.py       # Tier 3: Cross-feature interaction scenarios (10 complex scenarios)
└── test_tier4_real_world.py          # Tier 4: Real-world multi-step user journeys & sustained traffic (10 journeys)
```

### Tier Summary & Test Count

| Tier | Focus | Target Coverage | Total Tests |
|---|---|---|---|
| **Tier 1** | Feature Coverage | Features 1–27 (≥5 tests per feature) | 135 |
| **Tier 2** | Boundary & Corner Cases | Features 1–27 edge cases (≥5 tests per feature) | 135 |
| **Tier 3** | Cross-Feature Interactions | Security ↔ TV ↔ DB ↔ Music ↔ Movies ↔ Books | 10 |
| **Tier 4** | Real-World Application Scenarios | Multi-step user journeys, traffic bursts, 24-cycle pings | 10 |
| **Total** | Full E2E Verification Suite | R1–R5 & 27 Features in PROJECT.md | **290** |

---

## 3. Requirements (R1–R5) to Feature Mapping

| Requirement | Description | Associated Features | Test Files |
|---|---|---|---|
| **R1** | Rate Limiting, UptimeRobot IP Blocking, WAF & Project Errors | Features 1, 2, 3, 4, 5, 6 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py` |
| **R2** | TV Channel Streaming & Connectivity | Features 12, 13, 14, 15, 16 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py`, `test_tier4_real_world.py` |
| **R3** | Feature & UI Replication from @Zakirovsfilms_bot | Features 17, 18, 19, 20, 21 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py`, `test_tier4_real_world.py` |
| **R4** | Books Module Integration from @Zakirovs_ai | Features 22, 23, 24, 25 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py`, `test_tier4_real_world.py` |
| **R5** | Database Optimization & Concurrency | Features 7, 8, 9, 10, 11 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py`, `test_tier4_real_world.py` |
| **Quality** | Opaque-Box E2E Suite & Adversarial Hardening | Features 26, 27 | `test_tier1_feature_coverage.py`, `test_tier2_boundary_corner.py`, `test_tier3_cross_feature.py`, `test_tier4_real_world.py` |

---

## 4. Test Fixtures & Invariants (`conftest.py`)

- **`e2e_db_session`**: Creates an ephemeral in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) applying full declarative models, ensuring zero persistence between test cases.
- **`e2e_web_client`**: Instantiates the aiohttp application from `create_web_app()` with an ephemeral `TestServer` / `TestClient` for HTTP testing.
- **`clean_security_state`**: Automatically resets rate-limiter buckets and IP ban jails before and after each test.
- **`mock_bot`**: Provides a high-fidelity mock of the `aiogram.Bot` instance for validating message sends, document uploads, and callback queries without external Telegram network calls.

---

## 5. Execution Guide

Run the full E2E test suite:
```bash
pytest tests/e2e/ -v
```

Run specific tiers:
```bash
# Tier 1: Feature Coverage
pytest tests/e2e/test_tier1_feature_coverage.py -v

# Tier 2: Boundary & Corner Cases
pytest tests/e2e/test_tier2_boundary_corner.py -v

# Tier 3: Cross-Feature Combinations
pytest tests/e2e/test_tier3_cross_feature.py -v

# Tier 4: Real-World Scenarios
pytest tests/e2e/test_tier4_real_world.py -v
```
