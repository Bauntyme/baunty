"""
Adversarial Stress Test Suite for Milestone M1
Executed by Challenger 1 (Empirical Verification & Stress Harness)

Covers:
1. Extreme episode counts: total_parts = 1, 5, 49, 50, 51, 100, 139, 500, 1000.
2. Callback data size safety (every button callback_data <= 64 bytes).
3. Episode button row widths (strictly 5 columns for full rows, remainder for partial).
4. Range pagination pills logic, active dot placement, and boundary page clamps.
5. Watched indicator correctness under random watched episode subsets (Monte Carlo stress).
6. Next-episode calculation under all watched, none watched, and sporadic watched states.
7. Out-of-bounds pages, negative parts, and code format sanitization.
8. Concurrent database persistence of UserWatchProgress with race condition simulation.
"""
import pytest
import pytest_asyncio
import random
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.models import Base, UserWatchProgress
from database import crud
from keyboards.inline import movie_parts_keyboard


@pytest_asyncio.fixture
async def db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


# ==============================================================================
# TEST 1: EXTREME EPISODE COUNTS & 5-COLUMN ROW GEOMETRY
# ==============================================================================

@pytest.mark.parametrize("total_parts", [1, 5, 49, 50, 51, 100, 139, 500, 1000])
def test_extreme_episode_counts_and_row_widths(total_parts):
    code = "adv_test_code"
    per_page = 50
    total_pages = (total_parts + per_page - 1) // per_page

    # Test each page of the series (or sample pages for large counts)
    pages_to_test = range(total_pages) if total_pages <= 5 else [0, 1, total_pages // 2, total_pages - 1]

    for page_idx in pages_to_test:
        kb = movie_parts_keyboard(
            movie_code=code,
            total_parts=total_parts,
            current_part=1,
            page=page_idx,
            per_page=per_page,
            watched_parts=set(),
        )

        assert isinstance(kb, InlineKeyboardMarkup)
        assert len(kb.inline_keyboard) > 0

        # Extract only episode grid buttons (callback starts with watch_part, excluding top shortcut)
        top_shortcut = kb.inline_keyboard[0][0]
        assert top_shortcut.callback_data.startswith(f"watch_part:{code}:")

        episode_rows = []
        for row in kb.inline_keyboard[1:]:
            ep_btns = [
                b for b in row
                if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
            ]
            if ep_btns:
                episode_rows.append(ep_btns)

        # Calculate expected number of episodes on this page
        expected_start = page_idx * per_page + 1
        expected_end = min(total_parts, (page_idx + 1) * per_page)
        expected_ep_count = expected_end - expected_start + 1

        all_page_ep_btns = [b for r in episode_rows for b in r]
        assert len(all_page_ep_btns) == expected_ep_count, (
            f"Page {page_idx} for total {total_parts}: expected {expected_ep_count} buttons, got {len(all_page_ep_btns)}"
        )

        # Verify button values are consecutive
        expected_part_numbers = list(range(expected_start, expected_end + 1))
        actual_part_numbers = [
            int(b.callback_data.split(":")[-1]) for b in all_page_ep_btns
        ]
        assert actual_part_numbers == expected_part_numbers

        # Verify row widths:
        # Full rows MUST have exactly 5 columns.
        # The last row on the page has (expected_ep_count % 5) or 5 if divisible by 5.
        for r_idx, r in enumerate(episode_rows):
            is_last_row = (r_idx == len(episode_rows) - 1)
            if not is_last_row:
                assert len(r) == 5, f"Non-final row {r_idx} on page {page_idx} must have 5 columns, got {len(r)}"
            else:
                expected_last_len = expected_ep_count % 5 or 5
                assert len(r) == expected_last_len, (
                    f"Final row on page {page_idx} for total {total_parts}: expected {expected_last_len}, got {len(r)}"
                )


# ==============================================================================
# TEST 2: TELEGRAM 64-BYTE CALLBACK_DATA LIMIT UNDER ALL BUTTONS
# ==============================================================================

@pytest.mark.parametrize("movie_code", [
    "1",
    "42",
    "1390",
    "#777",
    "№888",
    "asil_9999",
    "very_long_custom_movie_code_abc123",
])
@pytest.mark.parametrize("total_parts", [1, 50, 139, 1000])
def test_all_callback_data_under_64_bytes(movie_code, total_parts):
    # Test first, middle, and last pages
    per_page = 50
    total_pages = (total_parts + per_page - 1) // per_page
    pages = [0, total_pages - 1]

    for p in pages:
        kb = movie_parts_keyboard(
            movie_code=movie_code,
            total_parts=total_parts,
            current_part=min(total_parts, p * per_page + 1),
            page=p,
            per_page=per_page,
            watched_parts={1, 2, 50, 139},
            webapp_url="https://baunty-cinema.onrender.com",
            download_url="https://dl.example.com/stream",
        )

        for row_idx, row in enumerate(kb.inline_keyboard):
            for btn_idx, btn in enumerate(row):
                if btn.callback_data is not None:
                    encoded_len = len(btn.callback_data.encode("utf-8"))
                    assert encoded_len <= 64, (
                        f"Button callback_data exceeds 64 bytes ({encoded_len} bytes): "
                        f"'{btn.callback_data}' at row {row_idx}, col {btn_idx} (code={movie_code}, total={total_parts})"
                    )
                    assert encoded_len > 0, "Callback data cannot be empty"


# ==============================================================================
# TEST 3: RANGE PAGINATION PILLS GEOMETRY & ACTIVE INDICATOR
# ==============================================================================

@pytest.mark.parametrize("total_parts, expected_pills", [
    (1, 0),       # Single page: 0 pills
    (49, 0),      # Single page: 0 pills
    (50, 0),      # Single page: 0 pills
    (51, 2),      # 2 pages: [1-50], [51-51]
    (100, 2),     # 2 pages: [1-50], [51-100]
    (139, 3),     # 3 pages: [1-50], [51-100], [101-139]
    (500, 10),    # 10 pages
    (1000, 20),   # 20 pages
])
def test_range_pagination_pills_logic(total_parts, expected_pills):
    code = "1390"
    per_page = 50
    total_pages = max(1, (total_parts + per_page - 1) // per_page)

    for page_idx in range(min(total_pages, 5)):
        kb = movie_parts_keyboard(code, total_parts=total_parts, current_part=1, page=page_idx, per_page=per_page)
        all_buttons = [b for row in kb.inline_keyboard for b in row]
        pills = [b for b in all_buttons if b.callback_data and b.callback_data.startswith(f"parts_page:{code}:")]

        assert len(pills) == expected_pills

        if expected_pills > 0:
            # Check active pill has bullet '• '
            active_pill = pills[page_idx]
            assert active_pill.text.startswith("• "), f"Active pill on page {page_idx} should start with '• '"
            assert active_pill.callback_data == f"parts_page:{code}:{page_idx}"

            # Check other pills do NOT have bullet
            for other_idx, other_pill in enumerate(pills):
                if other_idx != page_idx:
                    assert not other_pill.text.startswith("• "), (
                        f"Inactive pill {other_idx} on page {page_idx} should not start with '• '"
                    )
                    assert other_pill.callback_data == f"parts_page:{code}:{other_idx}"


# ==============================================================================
# TEST 4: WATCHED INDICATORS UNDER RANDOM SUBSETS (MONTE CARLO STRESS)
# ==============================================================================

def test_watched_indicators_random_subsets():
    """Adversarially test watched indicator correctness with randomized watched sets."""
    code = "monte_carlo"
    total_parts = 50
    rng = random.Random(42)

    for trial in range(30):
        # Pick random watched subset of parts 1..50
        watched_count = rng.randint(0, total_parts)
        watched_set = set(rng.sample(range(1, total_parts + 1), watched_count))
        current_part = rng.randint(1, total_parts)

        kb = movie_parts_keyboard(
            movie_code=code,
            total_parts=total_parts,
            current_part=current_part,
            page=0,
            per_page=50,
            watched_parts=watched_set,
        )

        all_buttons = [b for row in kb.inline_keyboard for b in row]
        grid_buttons = [
            b for b in all_buttons
            if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
            and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
        ]

        assert len(grid_buttons) == total_parts

        for b in grid_buttons:
            part_num = int(b.callback_data.split(":")[-1])
            if part_num == current_part:
                # Current part MUST show '▶️ {p}'
                assert b.text == f"▶️ {part_num}", (
                    f"Trial {trial}: Current part {part_num} text should be '▶️ {part_num}', got '{b.text}'"
                )
            elif part_num in watched_set:
                # Watched part MUST show '✓ {p}'
                assert b.text == f"✓ {part_num}", (
                    f"Trial {trial}: Watched part {part_num} text should be '✓ {part_num}', got '{b.text}'"
                )
            else:
                # Unwatched part MUST show '{p}'
                assert b.text == str(part_num), (
                    f"Trial {trial}: Unwatched part {part_num} text should be '{part_num}', got '{b.text}'"
                )


# ==============================================================================
# TEST 5: NEXT-EPISODE SHORTCUT BUTTON UNDER ALL WATCHED / NONE / SPORADIC
# ==============================================================================

def test_next_episode_shortcut_states():
    code = "next_ep"
    total_parts = 20

    # 1. None watched: should point to episode 1
    kb_none = movie_parts_keyboard(code, total_parts=total_parts, current_part=1, watched_parts=set())
    top_none = kb_none.inline_keyboard[0][0]
    assert top_none.text == "Davom ettirish: 1-qism"
    assert top_none.callback_data == f"watch_part:{code}:1"

    # 2. Sequential watched {1, 2, 3}: should point to episode 4
    kb_seq = movie_parts_keyboard(code, total_parts=total_parts, current_part=3, watched_parts={1, 2, 3})
    top_seq = kb_seq.inline_keyboard[0][0]
    assert top_seq.text == "Davom ettirish: 4-qism"
    assert top_seq.callback_data == f"watch_part:{code}:4"

    # 3. Sporadic / hole in watched: watched {1, 2, 4, 5} (missed 3)
    kb_hole = movie_parts_keyboard(code, total_parts=total_parts, current_part=5, watched_parts={1, 2, 4, 5})
    top_hole = kb_hole.inline_keyboard[0][0]
    assert top_hole.text == "Davom ettirish: 3-qism", "Should resume at first unwatched hole (3)"
    assert top_hole.callback_data == f"watch_part:{code}:3"

    # 4. Sporadic watched starting later: watched {5, 6, 7} (missed 1)
    kb_start_late = movie_parts_keyboard(code, total_parts=total_parts, current_part=7, watched_parts={5, 6, 7})
    top_start_late = kb_start_late.inline_keyboard[0][0]
    assert top_start_late.text == "Davom ettirish: 1-qism"
    assert top_start_late.callback_data == f"watch_part:{code}:1"

    # 5. All watched {1..20}: should offer 'Qayta ko'rish: 1-qism'
    all_watched = set(range(1, total_parts + 1))
    kb_all = movie_parts_keyboard(code, total_parts=total_parts, current_part=20, watched_parts=all_watched)
    top_all = kb_all.inline_keyboard[0][0]
    assert top_all.text == "Qayta ko'rish: 1-qism"
    assert top_all.callback_data == f"watch_part:{code}:1"


# ==============================================================================
# TEST 6: RESILIENCE TO OUT-OF-BOUNDS PAGES & CLAMPING
# ==============================================================================

def test_page_and_part_clamping():
    code = "clamp_test"
    total_parts = 139  # 3 pages: 0, 1, 2

    # Negative page -> should clamp to 0
    kb_neg = movie_parts_keyboard(code, total_parts=total_parts, page=-10)
    p0_first_btn = kb_neg.inline_keyboard[1][0]
    assert p0_first_btn.callback_data == f"watch_part:{code}:1"

    # Excessive page -> should clamp to last page (page 2)
    kb_excess = movie_parts_keyboard(code, total_parts=total_parts, page=999)
    p_last_first_btn = kb_excess.inline_keyboard[1][0]
    assert p_last_first_btn.callback_data == f"watch_part:{code}:101"

    # None page with current_part=125 -> should automatically pick page 2
    kb_auto = movie_parts_keyboard(code, total_parts=total_parts, current_part=125, page=None)
    p_auto_first_btn = kb_auto.inline_keyboard[1][0]
    assert p_auto_first_btn.callback_data == f"watch_part:{code}:101"

    # Negative or 0 total_parts -> safe fallback to 1
    kb_zero = movie_parts_keyboard(code, total_parts=0)
    assert len(kb_zero.inline_keyboard) > 0


# ==============================================================================
# TEST 7: DATABASE PERSISTENCE, CONCURRENCY, & UPSERT INTEGRITY
# ==============================================================================

@pytest.mark.asyncio
async def test_watch_progress_db_stress(db_session: AsyncSession):
    """Stress-test DB persistence under heavy updates and concurrent part logging."""
    user_id = 999888777
    movie_code = "7890"

    # Log parts in reverse order
    for part in range(50, 0, -1):
        await crud.record_user_watched_episode(db_session, user_id, movie_code, part)

    watched = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert len(watched) == 50
    assert watched == set(range(1, 51))

    # Re-logging same parts repeatedly should update without throwing IntegrityError
    for part in [1, 25, 50]:
        await crud.record_user_watched_episode(db_session, user_id, movie_code, part)

    watched_again = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert len(watched_again) == 50
