from services.chatgpt import ChatGPTService
import asyncio
from dotenv import load_dotenv
import csv
import os

load_dotenv()

async def main():
    print("Starting ChatGPTService...")
    chat_gpt = ChatGPTService()

    tasks = [chat_gpt.generate_response(20) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # Save results to a CSV file
    file_path = 'results.csv'
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Text', 'Netlist'])  # Write header only if file doesn't exist
        for result in results:
            for pair in result.pairs:
                writer.writerow([pair.text, pair.netlist])

    print("Results appended to results.csv")


if __name__ == "__main__":
    asyncio.run(main())