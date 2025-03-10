import os
import sys
import csv
from dotenv import load_dotenv
from collections import Counter
import requests
import json
import pandas as pd
from PyQt5 import uic
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QMessageBox,
    QFileDialog,
    QTableWidgetItem,
)

load_dotenv()
dexscreener_request_url = os.getenv("DEXSCREENER_REQUEST_URL")
gmgn_request_url = os.getenv("GMGN_REQUEST_URL")

Ui_MainWindow, QtBaseClass = uic.loadUiType("interface.ui")


class ProjectThread(QThread):
    result_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            self.result_signal.emit(self.get_top_project())
        except Exception as e:
            print(f"Error fetching top project data: {e}")
            self.result_signal.emit([])

    def get_top_project(self):
        url = f"{dexscreener_request_url}/get-top-project"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()["message"]
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"HTTP Request failed: {e}")
            return []


class PairAddressThread(QThread):
    result_signal = pyqtSignal(list)

    def __init__(self, contract_address):
        super().__init__()
        self.contract_address = contract_address

    def run(self):
        try:
            pair_address_list = self.pair_address_from_CA(self.contract_address)
            self.result_signal.emit([item["pairAddress"] for item in pair_address_list])
        except Exception as e:
            print(f"Error fetching pair address: {e}")
            self.result_signal.emit([])

    def pair_address_from_CA(self, contract_address):
        response = requests.get(
            f"https://api.dexscreener.com/token-pairs/v1/solana/{contract_address}",
            headers={},
        )
        return response.json()


class TraderThread(QThread):
    result_signal = pyqtSignal(list)

    def __init__(self, pair_address_list):
        super().__init__()
        self.pair_address_list = pair_address_list

    def run(self):
        try:
            self.result_signal.emit(self.dexscreener(self.pair_address_list))
        except Exception as e:
            print(f"Error fetching top trader data: {e}")
            self.result_signal.emit([])

    def dexscreener(self, pair_address_list):
        url = f"{dexscreener_request_url}/get-top-trader"
        headers = {"Content-Type": "application/json"}
        data = {"pair_address_list": pair_address_list}
        try:
            response = requests.get(url, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                return response.json()["message"]
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"HTTP Request failed: {e}")
            return []


class WalletThread(QThread):
    result_signal = pyqtSignal(list)

    def __init__(self, wallet_address_list):
        super().__init__()
        self.wallet_address_list = wallet_address_list

    def run(self):
        try:
            wallet_info_list = self.gmgn(self.wallet_address_list)
            self.result_signal.emit(wallet_info_list)
        except Exception as e:
            print(f"Error fetching wallet info: {e}")

    def gmgn(self, wallet_address_list):
        url = f"{gmgn_request_url}/get-wallet-info"
        headers = {"Content-Type": "application/json"}
        data = {"wallet_address_list": wallet_address_list}
        try:
            response = requests.get(url, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                response_data = response.json()
                return response_data["message"]
            else:
                print(f"Failed to retrieve data. Status code: {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"HTTP Request failed: {e}")
            return []


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Top Project Trakcer
        self.ui.get_top_project_btn.clicked.connect(self.get_top_project)
        self.ui.save_top_project_btn.clicked.connect(self.save_top_projects)

        # Pair Address from Dexscreener
        self.ui.get_pair_address_from_dex_btn.clicked.connect(
            self.get_pair_address_from_dex
        )
        self.ui.save_pair_address_from_dex_btn.clicked.connect(self.save_pair_address)

        # Top Trader Tracker
        self.ui.get_top_trader_btn.clicked.connect(self.get_top_trader)
        self.ui.save_top_trader_btn.clicked.connect(self.save_top_trader)

        # Excel Parser
        self.ui.import_removal_btn.clicked.connect(self.upload_removal_files)
        self.ui.remove_duplicates_btn.clicked.connect(self.remove_duplicates)
        self.ui.save_remove_duplicates_btn.clicked.connect(self.save_remove_duplicates)

        # Interest Wallet Tracker
        self.ui.import_duplicates_btn.clicked.connect(self.upload_duplicates_files)
        self.ui.extract_duplicates_btn.clicked.connect(self.extract_duplicates)
        self.ui.save_duplicates_btn.clicked.connect(self.save_duplicates)

        # GMGN Tracker
        self.ui.get_wallet_info_btn.clicked.connect(self.get_wallet_info)
        self.ui.save_wallet_info_btn.clicked.connect(self.save_wallet_info)

        self.wallet_address = ""
        self.contract_address = ""
        self.trader_thread = None
        self.running_pair_address_api = False
        self.running_dexscreener_api = False
        self.running_gmgn_api = False

    # Get top 30 projects on defined.fi (Top Project Tracker)
    def get_top_project(self):
        self.ui.top_project_viewer.clear()
        self.ui.get_top_project_btn.setEnabled(False)
        self.project_thread = ProjectThread()
        self.project_thread.result_signal.connect(self.load_top_projects)
        self.project_thread.start()

    def load_top_projects(self, output_contract_addresses):
        self.ui.top_project_viewer.setColumnCount(5)
        self.ui.top_project_viewer.setRowCount(len(output_contract_addresses))
        self.ui.top_project_viewer.setHorizontalHeaderLabels(
            ["Name", "Symbol", "Contract Address", "Volume"]
        )

        for row_index, item in enumerate(output_contract_addresses):
            self.ui.top_project_viewer.setItem(
                row_index, 0, QTableWidgetItem(str(item["token_name"]))
            )
            self.ui.top_project_viewer.setItem(
                row_index, 1, QTableWidgetItem(str(item["token_symbol"]))
            )
            self.ui.top_project_viewer.setItem(
                row_index, 2, QTableWidgetItem(str(item["contract_address"]))
            )
            self.ui.top_project_viewer.setItem(
                row_index, 3, QTableWidgetItem(str(item["volume"]))
            )

        self.ui.top_project_viewer.resizeColumnsToContents()
        self.ui.get_top_project_btn.setEnabled(True)

    def save_top_projects(self):
        if self.ui.top_project_viewer.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No top projects data to save!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Top Projects", "top_projects.csv", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                headers = [
                    "Name",
                    "Symbol",
                    "Contract Address",
                    "Volume",
                ]
                writer.writerow(headers)

                for row in range(self.ui.top_project_viewer.rowCount()):
                    row_data = []
                    for col in range(self.ui.top_project_viewer.columnCount()):
                        item = self.ui.top_project_viewer.item(row, col)
                        if item is not None:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Get pair address for given contract address on dexscreener using dexscreener api (Pair Address from Dexscreener)
    def get_pair_address_from_dex(self):
        self.contract_address = self.ui.contract_address.text()

        if len(self.contract_address) == 0:
            QMessageBox.warning(self, "Warning", "Input correct contract address!")
            return

        self.ui.pair_address_from_dex_viewer.clear()
        self.running_pair_address_api = True
        self.ui.get_pair_address_from_dex_btn.setEnabled(False)
        self.pair_address_thread = PairAddressThread(self.contract_address)
        self.pair_address_thread.result_signal.connect(self.load_pair_address)
        self.pair_address_thread.start()

    def load_pair_address(self, pair_address_list):
        try:
            for url in pair_address_list:
                self.ui.pair_address_from_dex_viewer.addItem(url)
            self.ui.get_pair_address_from_dex_btn.setEnabled(True)
            self.running_pair_address_api = False
        except Exception as e:
            print(f"Error loading JSON data: {e}")

    def save_pair_address(self):
        if self.running_pair_address_api == True:
            QMessageBox.warning(
                self, "Warning", "Pair Address API is running! Please wait a moment!"
            )
            return

        if self.ui.pair_address_from_dex_viewer.count() == 0:
            QMessageBox.warning(self, "Warning", "Not found pair address!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pair Addresses",
            f"{self.contract_address}.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        pair_address_list = [
            self.ui.pair_address_from_dex_viewer.item(i).text()
            for i in range(self.ui.pair_address_from_dex_viewer.count())
        ]

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Pair_Address",])
                for address in pair_address_list:
                    writer.writerow([address])

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Get top 100 traders for given pair address on dexscreener (Top Trader Tracker)
    def get_top_trader(self):
        pair_address_list = [
            item
            for item in self.ui.pair_address.toPlainText().split("\n")
            if item.strip()
        ]
        if not pair_address_list:
            QMessageBox.warning(self, "Warning", "Input one or more pair address!")
            return

        self.ui.top_trader_viewer.clear()
        self.running_dexscreener_api = True
        self.ui.get_top_trader_btn.setEnabled(False)
        self.trader_thread = TraderThread(pair_address_list)
        self.trader_thread.result_signal.connect(self.load_top_trader)
        self.trader_thread.start()

    def load_top_trader(self, top_trader_list):
        try:
            for url in top_trader_list:
                self.ui.top_trader_viewer.addItem(url)
            self.ui.get_top_trader_btn.setEnabled(True)
            self.running_dexscreener_api = False
        except Exception as e:
            print(f"Error loading JSON data: {e}")

    def save_top_trader(self):
        if self.running_dexscreener_api:
            QMessageBox.warning(
                self, "Warning", "Dexscreener API is running! Please wait a moment!"
            )
            return

        if self.ui.top_trader_viewer.count() == 0:
            QMessageBox.warning(self, "Warning", "No wallet addresses found!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Top Traders", "top_trader_list.csv", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                writer.writerow(["Wallet Address", "Rank"])

                top_trader_list = [
                    self.ui.top_trader_viewer.item(i).text()
                    for i in range(self.ui.top_trader_viewer.count())
                ]
                for index, value in enumerate(top_trader_list):
                    writer.writerow([value, (index % 100) + 1])

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Upload excel file to remove duplicates (Excel Parser)
    def upload_removal_files(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Excel Files",
            "",
            "Excel Files (*.xlsx; *.xls; *.csv)",
            options=options,
        )
        if file_name:
            self.ui.input_removal_file.clear()
            self.ui.input_removal_file.addItem(file_name)

    def remove_duplicates(self):
        if self.ui.input_removal_file.count() == 0:
            QMessageBox.warning(self, "Warning", "Please import an Excel or CSV file.")
            return

        file_path = self.ui.input_removal_file.item(0).text()

        if not (
            file_path.endswith(".xlsx")
            or file_path.endswith(".xls")
            or file_path.endswith(".csv")
        ):
            QMessageBox.warning(
                self,
                "Warning",
                "Unsupported file type! Please import an Excel or CSV file.",
            )
            self.ui.input_removal_file.clear()
            return

        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        df_cleaned = df.drop_duplicates(subset=["Wallet Address"], keep="first")

        self.show_removed_duplicates(df_cleaned)

    def show_removed_duplicates(self, df_cleaned):
        self.ui.remove_duplicates_viewer.setColumnCount(2)
        self.ui.remove_duplicates_viewer.setRowCount(len(df_cleaned))
        self.ui.remove_duplicates_viewer.setHorizontalHeaderLabels(
            ["Wallet Address", "Rank"]
        )

        for row_index, (_, row) in enumerate(df_cleaned.iterrows()):
            self.ui.remove_duplicates_viewer.setItem(
                row_index, 0, QTableWidgetItem(str(row["Wallet Address"]))
            )
            self.ui.remove_duplicates_viewer.setItem(
                row_index, 1, QTableWidgetItem(str(row["Rank"]))
            )

        self.ui.remove_duplicates_viewer.resizeColumnsToContents()

    def save_remove_duplicates(self):
        if self.ui.remove_duplicates_viewer.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No cleaned data to save!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Cleaned Data", "cleaned_data.csv", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                headers = ["Wallet Address", "Rank"]
                writer.writerow(headers)

                for row in range(self.ui.remove_duplicates_viewer.rowCount()):
                    row_data = []
                    for col in range(self.ui.remove_duplicates_viewer.columnCount()):
                        item = self.ui.remove_duplicates_viewer.item(row, col)
                        if item is not None:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Upload excel files to extract duplicates (Interest Wallet Tracker)
    def upload_duplicates_files(self):
        options = QFileDialog.Options()
        file_names, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Excel Files",
            "",
            "Excel Files (*.xlsx; *.xls; *.csv)",
            options=options,
        )
        if file_names:
            self.ui.input_duplicates_files.clear()
            for item in file_names:
                self.ui.input_duplicates_files.addItem(item)

    def extract_duplicates(self):
        if self.ui.input_duplicates_files.count() == 0:
            QMessageBox.warning(self, "Warning", "Please import an Excel or CSV file.")
            return

        file_paths = [
            self.ui.input_duplicates_files.item(i).text()
            for i in range(self.ui.input_duplicates_files.count())
        ]
        wallet_addresses = []

        for file_path in file_paths:
            if not (
                file_path.endswith(".xlsx")
                or file_path.endswith(".xls")
                or file_path.endswith(".csv")
            ):
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Unsupported file type: {file_path}! Please import Excel or CSV files only.",
                )
                continue

            try:
                if file_path.endswith(".csv"):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)

                if "Wallet Address" not in df.columns:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"'Wallet Address' column not found in {file_path}.",
                    )
                    continue

                wallet_addresses.extend(df["Wallet Address"].dropna().tolist())
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Error reading file {file_path}: {str(e)}"
                )

        item_counts = Counter(wallet_addresses)

        duplicated_dict_list = [
            {str(item): count} for item, count in item_counts.items() if count > 1
        ]

        sorted_duplicated_dict_list = sorted(
            duplicated_dict_list, key=lambda d: list(d.values())[0], reverse=True
        )

        self.show_duplicated_wallet(sorted_duplicated_dict_list)

    def show_duplicated_wallet(self, sorted_duplicated_dict_list):
        self.ui.duplicates_viewer.setColumnCount(2)
        self.ui.duplicates_viewer.setRowCount(len(sorted_duplicated_dict_list))
        self.ui.duplicates_viewer.setHorizontalHeaderLabels(
            ["Trader", "Duplicated count"]
        )

        for row_index, item in enumerate(sorted_duplicated_dict_list):
            for key, value in item.items():
                self.ui.duplicates_viewer.setItem(
                    row_index, 0, QTableWidgetItem(str(key))
                )
                self.ui.duplicates_viewer.setItem(
                    row_index, 1, QTableWidgetItem(str(value))
                )

        self.ui.duplicates_viewer.resizeColumnsToContents()

    def save_duplicates(self):
        if self.ui.duplicates_viewer.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No duplicated data to save!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Cleaned Data", "duplicated_data.csv", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                headers = ["Trader", "Duplicated count"]
                writer.writerow(headers)

                for row in range(self.ui.duplicates_viewer.rowCount()):
                    row_data = []
                    for col in range(self.ui.duplicates_viewer.columnCount()):
                        item = self.ui.duplicates_viewer.item(row, col)
                        if item is not None:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Get wallet information on gmgn.ai
    def get_wallet_info(self):
        wallet_address_list = [
            item
            for item in self.ui.wallet_address.toPlainText().split("\n")
            if item.strip()
        ]
        if not wallet_address_list:
            QMessageBox.warning(self, "Warning", "Input one or more wallet address!")
            return

        self.ui.wallet_info_viewer.clear()
        self.running_gmgn_api = True
        self.ui.get_wallet_info_btn.setEnabled(False)
        self.wallet_thread = WalletThread(wallet_address_list)
        self.wallet_thread.result_signal.connect(self.load_wallet_info)
        self.wallet_thread.start()

    def load_wallet_info(self, wallet_info_list):
        if len(wallet_info_list) == 0:
            QMessageBox.warning(
                self, "Warning", "No wallets matching your filter were found!"
            )
            self.ui.get_wallet_info_btn.setEnabled(True)
            self.running_gmgn_api = False
            return

        self.wallet_info_list = wallet_info_list
        self.ui.wallet_info_viewer.setColumnCount(11)
        self.ui.wallet_info_viewer.setRowCount(len(wallet_info_list))
        self.ui.wallet_info_viewer.setHorizontalHeaderLabels(
            [
                "Wallet Address",
                "Win Rate",
                "Transactions",
                "PnL",
                "Distribution",
                "500%",
                "200% ~ 500%",
                "0% ~ 200%",
                "0% ~ -50%",
                "-50%",
                "10 Sec Dump",
            ]
        )

        for row_index, item in enumerate(wallet_info_list):
            self.load_one_wallet_info(row_index, item)
        self.ui.wallet_info_viewer.resizeColumnsToContents()
        self.ui.get_wallet_info_btn.setEnabled(True)
        self.running_gmgn_api = False

    def load_one_wallet_info(self, row_index, item):
        self.ui.wallet_info_viewer.setItem(
            row_index, 0, QTableWidgetItem(str(item["wallet_address"]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 1, QTableWidgetItem(str(item["win_rate"]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 2, QTableWidgetItem(str(item["transactions"]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 3, QTableWidgetItem(str(item["pnl"]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 4, QTableWidgetItem(str(item["distribution_num"]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 5, QTableWidgetItem(str(item["distribution"][0]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 6, QTableWidgetItem(str(item["distribution"][1]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 7, QTableWidgetItem(str(item["distribution"][2]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 8, QTableWidgetItem(str(item["distribution"][3]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 9, QTableWidgetItem(str(item["distribution"][4]))
        )
        self.ui.wallet_info_viewer.setItem(
            row_index, 10, QTableWidgetItem(str(item["dumps"]))
        )

    def save_wallet_info(self):
        if self.running_gmgn_api == True:
            QMessageBox.warning(
                self, "Warning", "GMGN API is running! Please wait a moment!"
            )
            return

        row_count = self.ui.wallet_info_viewer.rowCount()
        column_count = self.ui.wallet_info_viewer.columnCount()

        if row_count == 0:
            QMessageBox.warning(self, "Warning", "Not found wallet address!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Wallet Info", "wallet_info.csv", "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                headers = [
                    "Wallet Address",
                    "Win Rate",
                    "Transactions",
                    "PnL",
                    "Distribution",
                    "500%",
                    "200% ~ 500%",
                    "0% ~ 200%",
                    "0% ~ -50%",
                    "-50%",
                    "10 Sec Dumps",
                ]
                writer.writerow(headers)

                for row in range(row_count):
                    row_data = []
                    for col in range(column_count):
                        item = self.ui.wallet_info_viewer.item(row, col)
                        if item is not None:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Success",
                f"Saved as CSV file successfully!\nLocation: {file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred while saving the file:\n{str(e)}"
            )

    # Close app
    def open(self):
        self.open()

    def reject(self):
        self.close()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
