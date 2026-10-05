import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fast_flights import FlightQuery, Passengers, create_query, get_flights

ROUTES = [("DEL", "BOM"), ("BOM", "DEL"), ("BLR", "DEL"), ("DEL", "BLR"),
          ("BOM", "BLR"), ("DEL", "CCU"), ("PNQ", "DEL"), ("HYD", "DEL")]
DAYS_AHEAD = [1, 3, 7, 14, 21, 30, 45, 60]

IST = ZoneInfo("Asia/Kolkata")          # always use India time, even on US servers
DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def build_query(flight_date, origin, dest):
    """Build the search. Ask for rupees if this library version supports it."""
    args = dict(
        flights=[FlightQuery(date=flight_date, from_airport=origin, to_airport=dest)],
        trip="one-way",
        seat="economy",
        passengers=Passengers(adults=1),
        language="en-US",
    )
    try:
        return create_query(**args, currency="INR"), "INR"
    except TypeError:
        return create_query(**args), "unknown"


def to_datetime(sdt):
    """Turn the library's date=(2026,10,6), time=(0,15) into a normal datetime."""
    y, m, d = sdt.date
    t = tuple(sdt.time or ())
    hour = t[0] if len(t) > 0 else 0
    minute = t[1] if len(t) > 1 else 0
    return datetime(y, m, d, hour, minute)


def flight_to_row(f, scraped_at, flight_date, days_left, origin, dest, currency):
    """Flatten one ticket option into one row of simple columns."""
    legs = f.flights
    dep = to_datetime(legs[0].departure)
    arr = to_datetime(legs[-1].arrival)
    total_min = int((arr - dep).total_seconds() // 60)
    flying_min = sum(leg.duration or 0 for leg in legs)
    carbon = getattr(f, "carbon", None)

    return {
        "scraped_on": scraped_at.date().isoformat(),
        "scraped_at": scraped_at.strftime("%Y-%m-%d %H:%M"),
        "flight_date": flight_date,
        "days_left": days_left,
        "origin": origin,
        "destination": dest,
        "route": f"{origin}-{dest}",
        "airline_code": f.type,
        "airlines": " + ".join(f.airlines),
        "num_airlines": len(set(f.airlines)),
        "price": f.price,
        "currency": currency,
        "num_stops": len(legs) - 1,
        "layover_airports": " ".join(leg.to_airport.code for leg in legs[:-1]),
        "dep_time": dep.strftime("%H:%M"),
        "dep_hour": dep.hour,
        "arr_time": arr.strftime("%H:%M"),
        "arr_hour": arr.hour,
        "arrives_next_day": arr.date() > dep.date(),
        "total_duration_min": total_min,
        "flying_min": flying_min,
        "layover_min": total_min - flying_min,
        "plane_types": " | ".join(leg.plane_type or "" for leg in legs),
        "carbon_kg": carbon.emission / 1000 if carbon and carbon.emission else None,
        "carbon_typical_kg": carbon.typical_on_route / 1000 if carbon and carbon.typical_on_route else None,
    }


def main():
    scraped_at = datetime.now(IST)
    today = scraped_at.date()
    rows, failures = [], []

    for origin, dest in ROUTES:
        for d in DAYS_AHEAD:
            flight_date = (today + timedelta(days=d)).isoformat()

            for attempt in range(2):          # try up to 2 times
                try:
                    query, currency = build_query(flight_date, origin, dest)
                    results = get_flights(query) or []
                    for f in results:
                        try:
                            rows.append(flight_to_row(f, scraped_at, flight_date, d, origin, dest, currency))
                        except Exception as e:
                            failures.append(f"Bad row {origin}-{dest} {flight_date}: {e}")
                    print(f"{origin}-{dest} {flight_date}: {len(results)} options")
                    break                      # success, stop retrying
                except Exception as e:
                    if attempt == 0:
                        print(f"Retrying {origin}-{dest} {flight_date}...")
                        time.sleep(30)         # wait a bit, then try once more
                    else:
                        failures.append(f"Search failed {origin}-{dest} {flight_date}: {e}")

            time.sleep(random.uniform(5, 12))   # be polite between searches

    df = pd.DataFrame(rows).drop_duplicates()
    out = DATA_DIR / f"flights_{today.isoformat()}.csv"
    df.to_csv(out, index=False)

    print(f"\nSaved {len(df)} rows to {out}")
    if failures:
        print(f"{len(failures)} problems:")
        for msg in failures:
            print("  ", msg)
            

if __name__ == "__main__":
    main()