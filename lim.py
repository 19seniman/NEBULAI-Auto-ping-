import hashlib
import time
import aiohttp
import asyncio
import numpy as np
import os
import concurrent.futures
from typing import Optional, Tuple

class Logger:
    colors = {
        "cyan": "\033[96m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "green": "\033[92m",
        "magenta": "\033[95m",
        "blue": "\033[94m",
        "white": "\033[97m",
        "gray": "\033[90m",
        "bold": "\033[1m",
        "reset": "\033[0m"
    }

    @staticmethod
    def info(msg):
        print(f"{Logger.colors['cyan']}[i] {msg}{Logger.colors['reset']}")

    @staticmethod
    def warn(msg):
        print(f"{Logger.colors['yellow']}[!] {msg}{Logger.colors['reset']}")

    @staticmethod
    def error(msg):
        print(f"{Logger.colors['red']}[x] {msg}{Logger.colors['reset']}")

    @staticmethod
    def success(msg):
        print(f"{Logger.colors['green']}[+] {msg}{Logger.colors['reset']}")

    @staticmethod
    def loading(msg):
        print(f"{Logger.colors['magenta']}[*] {msg}{Logger.colors['reset']}")

    @staticmethod
    def step(msg):
        print(f"{Logger.colors['blue']}[>] {Logger.colors['bold']}{msg}{Logger.colors['reset']}")

    @staticmethod
    def critical(msg):
        print(f"{Logger.colors['red']}{Logger.colors['bold']}[FATAL] {msg}{Logger.colors['reset']}")

    @staticmethod
    def summary(msg):
        print(f"{Logger.colors['green']}{Logger.colors['bold']}[SUMMARY] {msg}{Logger.colors['reset']}")

    @staticmethod
    def banner():
        border = f"{Logger.colors['blue']}{Logger.colors['bold']}╔═════════════════════════════════════════╗{Logger.colors['reset']}"
        title = f"{Logger.colors['blue']}{Logger.colors['bold']}║  🍉 19Seniman From Insider  🍉   ║{Logger.colors['reset']}"
        bottom_border = f"{Logger.colors['blue']}{Logger.colors['bold']}╚═════════════════════════════════════════╝{Logger.colors['reset']}"
        print(f"\n{border}")
        print(f"{title}")
        print(f"{bottom_border}\n")

    @staticmethod
    def section(msg):
        line = '─' * 40
        print(f"\n{Logger.colors['gray']}{line}{Logger.colors['reset']}")
        if msg:
            print(f"{Logger.colors['white']}{Logger.colors['bold']} {msg} {Logger.colors['reset']}")
        print(f"{Logger.colors['gray']}{line}{Logger.colors['reset']}\n")

    @staticmethod
    def countdown(msg):
        print(f"\r{Logger.colors['blue']}[⏰] {msg}{Logger.colors['reset']}", end="", flush=True)

def generate_matrix(seed: int, size: int) -> np.ndarray:
    """Generates a matrix of a given size using a pseudo-random seed."""
    matrix = np.empty((size, size), dtype=np.float64)
    current_seed = seed
    a, b = 0x4b72e682d, 0x2675dcd22
    for i in range(size):
        for j in range(size):
            value = (a * current_seed + b) % 1000
            matrix[i][j] = float(value)
            current_seed = value
    return matrix

def multiply_matrices(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Multiplies two matrices."""
    return a @ b

def flatten_matrix(matrix: np.ndarray) -> str:
    """Flattens a matrix into a single string."""
    return ''.join(f"{x:.0f}" for x in matrix.flat)

async def compute_hash_mod(matrix: np.ndarray, mod: int = 10**7) -> int:
    """Computes a SHA256 hash and takes a modulus."""
    flat_str = flatten_matrix(matrix)
    sha256 = hashlib.sha256(flat_str.encode()).hexdigest()
    return int(int(sha256, 16) % mod)

async def fetch_task(session: aiohttp.ClientSession, token: str) -> Tuple[dict, bool]:
    """Fetches a new task from the API."""
    headers = {"Content-Type": "application/json", "token": token}
    try:
        Logger.loading("Fetching task...")
        # URL untuk mengambil tugas
        async with session.post("https://nebulai.network/open_compute/finish/task", json={}, headers=headers, timeout=10) as resp:
            data = await resp.json()
            if data.get("code") == 0:
                Logger.info("Task fetched successfully.")
                return data['data'], True
            Logger.warn(f"API returned error code: {data.get('code')}")
            return None, False
    except Exception as e:
        Logger.error(f"Fetch error: {str(e)}")
        return None, False

async def submit_results(session: aiohttp.ClientSession, token: str, r1: float, r2: float, task_id: str) -> bool:
    """Submits the computed results to the API."""
    headers = {"Content-Type": "application/json", "token": token}
    payload = {"result_1": f"{r1:.10f}", "result_2": f"{r2:.10f}", "task_id": task_id}
    try:
        Logger.loading("Submitting results...")
        # URL untuk mengirim hasil
        async with session.post("https://nebulai.network/open_compute/submit/task", json=payload, headers=headers, timeout=10) as resp:
            data = await resp.json()
            if data.get("code") == 0 and data.get("data", {}).get("calc_status", False):
                Logger.success("Results submitted successfully.")
                return True
            Logger.warn("Submission failed.")
            return False
    except Exception as e:
        Logger.error(f"Submit error: {str(e)}")
        return False

async def process_task(task_data: dict) -> Optional[Tuple[float, float]]:
    """Processes a single task, including matrix generation and computation."""
    seed1, seed2, size = task_data["seed1"], task_data["seed2"], task_data["matrix_size"]
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            t0 = time.time() * 1000
            Logger.step("Generating matrices...")
            A_future = executor.submit(generate_matrix, seed1, size)
            B_future = executor.submit(generate_matrix, seed2, size)
            A, B = await asyncio.gather(
                asyncio.wrap_future(A_future),
                asyncio.wrap_future(B_future)
            )
            Logger.info("Matrices generated successfully.")
        
        Logger.step("Multiplying matrices...")
        C = multiply_matrices(A, B)
        
        Logger.step("Computing hash...")
        f = await compute_hash_mod(C)
        t1 = time.time() * 1000
        
        result_1 = t0 / f
        result_2 = f / (t1 - t0) if (t1 - t0) != 0 else 0
        
        Logger.summary(f"Computation complete. Result 1: {result_1:.4f}, Result 2: {result_2:.4f}")
        return result_1, result_2
    except Exception as e:
        Logger.error(f"Process error: {str(e)}")
        return None

async def worker_loop(token: str):
    """Main worker loop for a single token."""
    async with aiohttp.ClientSession() as session:
        while True:
            task_data, success = await fetch_task(session, token)
            if not success:
                Logger.warn("Failed to fetch task, retrying in 2 seconds...")
                await asyncio.sleep(2)
                continue
            
            results = await process_task(task_data)
            if not results:
                Logger.warn("Failed to process task, retrying in 1 second...")
                await asyncio.sleep(1)
                continue
            
            submitted = await submit_results(session, token, results[0], results[1], task_data["task_id"])
            await asyncio.sleep(0.5 if submitted else 3)

async def main():
    """Main function to start the worker loops."""
    Logger.banner()
    if not os.path.exists("data.txt"):
        Logger.critical("data.txt not found! Exiting.")
        return
    
    with open("data.txt") as f:
        data = [line.strip() for line in f if line.strip()]
    
    if not data:
        Logger.critical("No data in data.txt! Exiting.")
        return
    
    Logger.info(f"Starting worker loops for {len(data)} tokens...")
    await asyncio.gather(*(worker_loop(token) for token in data))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.warn("Stopped by user")
