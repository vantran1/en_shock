"""Growing windows for Stage 2 (methodology v5, Section 3.4): the months in which the crop
harvested in a quarter was in the field, as lags from the last month of the harvest quarter
(0 = last month). Shared by scripts/build_rice_calendar.py and scripts/build_corn_calendar.py."""
from datetime import date, timedelta


def month_of(doy) -> int:
    """Calendar month (1-12) of a day of year (non-leap year)."""
    return (date(2001, 1, 1) + timedelta(days=int(doy) - 1)).month


def window(plant_month: int, harvest_month: int, q: int) -> list:
    """Lags of the window from planting month to harvest month, for the crop harvested in
    quarter q. The harvest month is moved into the quarter when it falls outside it (the crop
    harvested in the quarter cannot have been harvested before or after it), keeping the
    season's length."""
    q_end = 3 * q
    length = (harvest_month - plant_month) % 12
    harvest = q_end - ((q_end - harvest_month) % 12)  # harvest month at or before the quarter end
    if harvest - q_end <= -6:  # nearer to the next cycle
        harvest += 12
    harvest = min(max(harvest, q_end - 2), q_end)
    return [q_end - m for m in range(harvest - length, harvest + 1)]
