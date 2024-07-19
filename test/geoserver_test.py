import asyncio
import aiohttp
import time
import io
from PIL import Image
import csv
import random
from collections import defaultdict

# Define the overall bounding box and other parameters
OVERALL_BBOX = (143.83482400000003, -43.648056, 148.47914100000003, -39.573891)

## For the GeoServer Cloud mode use those ones instead...
# BASE_HOST = "http://localhost:8080"
# GEOSERVER_PATH = "/geoserver/cloud/ows"
BASE_HOST = "http://localhost"
GEOSERVER_PATH = "/geoserver/ows"

LAYERS = [
    "topp:tasmania_state_boundaries",
    "topp:tasmania_roads",
    "topp:tasmania_cities",
]
CRS = "EPSG:4326"
STYLES = ""  # Empty string for default styles
WMS_VERSION = "1.1.1"


def generate_random_bbox(overall_bbox):
    min_x, min_y, max_x, max_y = overall_bbox
    width = max_x - min_x
    height = max_y - min_y

    x1 = min_x + random.random() * width * 0.8
    y1 = min_y + random.random() * height * 0.8
    x2 = x1 + random.random() * (max_x - x1)
    y2 = y1 + random.random() * (max_y - y1)

    return f"{x1},{y1},{x2},{y2}"


def generate_random_dimensions():
    width = random.randint(300, 1000)
    height = random.randint(200, 800)
    return width, height


async def make_request(session, timeout=5):
    bbox = generate_random_bbox(OVERALL_BBOX)
    width, height = generate_random_dimensions()

    url = (
        f"{BASE_HOST}{GEOSERVER_PATH}"
        f"?request=GetMap"
        f"&service=WMS"
        f"&version={WMS_VERSION}"
        f"&layers={','.join(LAYERS)}"
        f"&styles={STYLES}"
        f"&srs={CRS}"
        f"&bbox={bbox}"
        f"&width={width}"
        f"&height={height}"
        f"&format=image%2Fpng"
    )

    start_time = time.time()
    try:
        async with session.get(url, timeout=timeout) as response:
            content = await response.read()
            end_time = time.time()

            response_time = end_time - start_time
            is_valid = response.status == 200

            try:
                img = Image.open(io.BytesIO(content))
                is_valid_png = img.format == "PNG"
            except:
                is_valid_png = False

            is_valid = is_valid and is_valid_png and response_time <= timeout

    except asyncio.TimeoutError:
        response_time = timeout
        is_valid = False
    except Exception:
        response_time = time.time() - start_time
        is_valid = False

    return {"response_time": response_time, "is_valid": is_valid}


async def run_test(num_requests, concurrency, ramp_up_time=0):
    async with aiohttp.ClientSession() as session:
        start_time = time.time()

        async def delayed_request(delay):
            await asyncio.sleep(delay)
            return await make_request(session)

        if ramp_up_time > 0:
            delays = [random.uniform(0, ramp_up_time) for _ in range(num_requests)]
        else:
            delays = [0] * num_requests

        tasks = [delayed_request(delay) for delay in delays]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()

    total_time = end_time - start_time
    valid_requests = sum(
        1 for result in results if isinstance(result, dict) and result["is_valid"]
    )
    response_times = [
        result["response_time"] for result in results if isinstance(result, dict)
    ]

    avg_response_time = (
        sum(response_times) / len(response_times) if response_times else 0
    )
    throughput = num_requests / total_time

    # Calculate additional metrics
    errors = sum(1 for result in results if isinstance(result, Exception))
    timeouts = sum(
        1
        for result in results
        if isinstance(result, dict)
        and not result["is_valid"]
        and result["response_time"] >= 5
    )

    # Calculate response time distribution
    response_time_distribution = defaultdict(int)
    for rt in response_times:
        bucket = round(rt, 1)  # Round to nearest 0.1s
        response_time_distribution[bucket] += 1

    return {
        "concurrency": concurrency,
        "total_requests": num_requests,
        "valid_requests": valid_requests,
        "avg_response_time": avg_response_time,
        "throughput": throughput,
        "total_time": total_time,
        "errors": errors,
        "timeouts": timeouts,
        "response_time_distribution": dict(response_time_distribution),
    }


async def find_optimal_concurrency(
    initial_requests=100,
    concurrency_start=1,
    concurrency_step=10,
    concurrency_max=1000,
    ramp_up_time=5,
):
    max_throughput = 0
    optimal_concurrency = 0

    for concurrency in range(concurrency_start, concurrency_max + 1, concurrency_step):
        result = await run_test(initial_requests, concurrency, ramp_up_time)

        print(f"Concurrency: {concurrency}")
        print(f"Throughput: {result['throughput']:.2f} requests/second")
        print(
            f"Valid requests: {result['valid_requests']} / {result['total_requests']}"
        )
        print(f"Errors: {result['errors']}, Timeouts: {result['timeouts']}")
        print("---")

        if result["valid_requests"] < result["total_requests"]:
            print("Invalid requests detected. Consider reducing concurrency.")
            if optimal_concurrency == 0:
                optimal_concurrency = max(1, concurrency - concurrency_step)
            break

        if result["throughput"] > max_throughput:
            max_throughput = result["throughput"]
            optimal_concurrency = concurrency
        elif result["throughput"] < max_throughput * 0.7:  # 30% decrease
            break

    print(f"Optimal concurrency: {optimal_concurrency}")
    return optimal_concurrency


async def main():
    ramp_up_time = 0  # Set the desired ramp-up time in seconds
    optimal_concurrency = await find_optimal_concurrency(ramp_up_time=ramp_up_time)

    num_requests_start = 100
    num_requests_step = 100
    num_requests_max = 10000
    max_throughput = 0
    optimal_num_requests = 0
    results = []

    with open("test_results.csv", "w", newline="") as csvfile:
        fieldnames = [
            "num_requests",
            "concurrency",
            "total_requests",
            "valid_requests",
            "avg_response_time",
            "throughput",
            "total_time",
            "errors",
            "timeouts",
            "ramp_up_time",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for num_requests in range(
            num_requests_start, num_requests_max + 1, num_requests_step
        ):
            result = await run_test(num_requests, optimal_concurrency, ramp_up_time)
            result["num_requests"] = num_requests
            result["ramp_up_time"] = ramp_up_time
            results.append(result)
            writer.writerow(
                {k: v for k, v in result.items() if k != "response_time_distribution"}
            )

            print(f"Number of requests: {num_requests}")
            print(f"Ramp-up time: {ramp_up_time} seconds")
            print(f"Throughput: {result['throughput']:.2f} requests/second")
            print(
                f"Valid requests: {result['valid_requests']} / {result['total_requests']}"
            )
            print(f"Errors: {result['errors']}, Timeouts: {result['timeouts']}")
            print("Response time distribution:")
            for rt, count in sorted(result["response_time_distribution"].items()):
                print(f"  {rt:.1f}s: {count}")
            print("---")

            if result["valid_requests"] < result["total_requests"]:
                print("Invalid requests detected. Exiting the loop.")
                break

            if result["throughput"] > max_throughput:
                max_throughput = result["throughput"]
                optimal_num_requests = num_requests
            elif result["throughput"] < max_throughput * 0.7:  # 30% decrease
                break

    print(f"Maximum throughput: {max_throughput:.2f} requests/second")
    print(f"Optimal number of requests: {optimal_num_requests}")
    print(f"Optimal concurrency: {optimal_concurrency}")


if __name__ == "__main__":
    asyncio.run(main())
