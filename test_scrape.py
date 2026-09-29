from datetime import date, timedelta
from fast_flights import FlightQuery, Passengers, create_query, get_flights

flight_date = (date.today() + timedelta(days=7)).isoformat()

query = create_query(
    flights=[FlightQuery(date=flight_date, from_airport="DEL", to_airport="BOM")],
    trip="one-way",
    seat="economy",
    passengers=Passengers(adults=1),
    language="en-US",
)

results = get_flights(query)

print("Flights found:", len(results))
print("\nFull details of the first flight:")
print(results[0])

print("\nFirst 5 flights:")
for f in results[:6]:
    print(f.airlines, "|", f.price)