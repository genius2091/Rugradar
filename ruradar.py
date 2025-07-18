#!/usr/bin/env python3
import os
import time
import logging
from web3 import Web3
import requests
from dotenv import load_dotenv
import schedule

# Load configuration from .env
load_dotenv()

ETH_NODE = os.getenv('ETH_NODE_URL')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# List of Uniswap V2-like pair contract addresses to monitor\PAIR_ADDRESSES = [
    # Пример: '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',  # USDC-WETH
]

# Порог сжигания LP токенов в процентах для оповещения
THRESHOLD_PERCENT = float(os.getenv('THRESHOLD_PERCENT', 50.0))
# Интервал проверки в секундах
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL_SECONDS', 60))

if not ETH_NODE or not BOT_TOKEN or not CHAT_ID:
    logging.error("Не заданы ETH_NODE_URL, TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в .env")
    exit(1)

# Подключение к Ethereum-ноде
w3 = Web3(Web3.HTTPProvider(ETH_NODE))
if not w3.isConnected():
    logging.error("Не удалось подключиться к узлу Ethereum")
    exit(1)

# ABI для событий Transfer и функции totalSupply
abi = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

# Храним предыдущие значения totalSupply
previous_supply = {}

def send_telegram(message):
    """Отправить уведомление в Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': message}
    resp = requests.post(url, data=data)
    if resp.status_code != 200:
        logging.warning(f"Не удалось отправить сообщение в Telegram: {resp.text}")


def monitor_pair(pair_address):
    """Проверяет пару на сжигание LP токенов."""
    contract = w3.eth.contract(address=Web3.toChecksumAddress(pair_address), abi=abi)
    current_supply = contract.functions.totalSupply().call()
    prev = previous_supply.get(pair_address, current_supply)
    if current_supply < prev:
        burned = prev - current_supply
        percent = burned / prev * 100
        if percent >= THRESHOLD_PERCENT:
            message = (
                f"🚨 RugRadar Alert 🚨\n"  
                f"Пара {pair_address} сожгла {burned} LP токенов ({percent:.2f}% от общего объема).\n"
                f"Порог: {THRESHOLD_PERCENT}%"
            )
            send_telegram(message)
    previous_supply[pair_address] = current_supply


def monitor_all():
    logging.info("Запуск цикла мониторинга")
    for pair in PAIR_ADDRESSES:
        try:
            monitor_pair(pair)
        except Exception as e:
            logging.error(f"Ошибка при мониторинге {pair}: {e}")


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    # Начальная проверка
    monitor_all()
    # Плановый запуск каждые CHECK_INTERVAL секунд
    schedule.every(CHECK_INTERVAL).seconds.do(monitor_all)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
