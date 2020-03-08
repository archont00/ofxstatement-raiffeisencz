import csv
from datetime import datetime
import re

from ofxstatement import statement
from ofxstatement.parser import CsvStatementParser
from ofxstatement.plugin import Plugin
#from ofxstatement.statement import Statement


class RaiffeisenCZPlugin(Plugin):
    """Raiffeisenbank, a.s. (Czech Republic) (CSV, cp1250)
    """

    def get_parser(self, filename):
        # Open input file and set some defaults
        RaiffeisenCZPlugin.encoding = self.settings.get('charset', 'cp1250')
        f = open(filename, "r", encoding=RaiffeisenCZPlugin.encoding)
        parser = RaiffeisenCZParser(f)
        parser.statement.currency = self.settings.get('currency', 'CZK')
        parser.statement.bank_id = self.settings.get('bank', 'RZBCCZPP')
        parser.statement.account_id = self.settings.get('account', '')
        parser.statement.account_type = self.settings.get('account_type', 'CHECKING')
        parser.statement.trntype = "OTHER"
        return parser


class RaiffeisenCZParser(CsvStatementParser):

    # GnuCash recognises the following descriptive fields:
    # - Header for Transaction Journal:
    #   - Description
    #   - Notes
    # - Line item memo for each account in a single Transaction Journal:
    #   - Memo
    #
    # .payee is assigned to "Description" in GnuCash
    # .memo is assigned to "Memo" in GnuCash and also concatenated
    #       to "Notes" after "OFX ext. info" and "Trans type"
    #
    # When .payee is empty, GnuCash assigns .memo to:
    # - "Description" and does not concatenate to "Notes"
    # - "Memo"
    #
    # Although ofxstatement can create bank_account_to, GnuCash ignores it.
    #
    # In GnuCash, .check_no (if empty, then .refnum) is assigned to "Num".
    #
    # The approach is:
    # - merge counterparty name (.payee) + account number + bank code
    # - merge pmt reference (.memo) + other payment specifics (VS, KS, SS)

    date_format = "%d.%m.%Y %H:%M"
    date_format_user = "%d.%m.%Y"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.columns = None
        self.mappings = None

    def split_records(self):
        return csv.reader(self.fin, delimiter=';', quotechar='"')

    def parse_record(self, line):
        """Parse given transaction line and return StatementLine object
        """

        # First line of CSV file contains headers, not an actual transaction
        if self.cur_record == 1:
            # Prepare columns headers lookup table for parsing
            # v ... column heading
            # i ... column index (expected by .mappings)
            self.columns = {v: i for i,v in enumerate(line)}
            # .date_user cannot be parsed by super().parse_record(line)
            # because of different date_format_user
            self.mappings = {
                "date":      self.columns['Datum zaúčtování'],
                "memo":      self.columns['Zpráva'],
                "payee":     self.columns['Název protiúčtu'],
                "amount":    self.columns['Zaúčtovaná částka'],
                "check_no":  self.columns['VS'],
                "refnum":    self.columns['Id transakce'],
            }

            # And skip further processing by parser
            return None

        # Shortcut
        columns = self.columns

        # Normalize string
        for i,v in enumerate(line):
            line[i] = v.strip()

        if line[columns["Zaúčtovaná částka"]] == "":
            line[columns["Zaúčtovaná částka"]] = "0"

        if line[columns["Poplatek"]] == "":
            line[columns["Poplatek"]] = "0"

        StatementLine = super(RaiffeisenCZParser, self).parse_record(line)

        StatementLine.id = statement.generate_transaction_id(StatementLine)

        if not line[columns["Datum provedení"]] == "":
            StatementLine.date_user = datetime.strptime(line[columns["Datum provedení"]], self.date_format_user)

        if   line[columns["Typ transakce"]].startswith("Převod"):
            StatementLine.trntype = "XFER"
        elif line[columns["Typ transakce"]].startswith("Platba"):
            StatementLine.trntype = "XFER"
        elif line[columns["Typ transakce"]].startswith("Jednorázová platba"):
            StatementLine.trntype = "XFER"
        elif line[columns["Typ transakce"]].startswith("Příchozí platba"):
            StatementLine.trntype = "CREDIT"
        elif line[columns["Typ transakce"]].startswith("Trvalý převod"):
            StatementLine.trntype = "REPEATPMT"
        elif line[columns["Typ transakce"]].startswith("Trvalá platba"):
            StatementLine.trntype = "REPEATPMT"
        elif line[columns["Typ transakce"]].startswith("Kladný úrok"):
            StatementLine.trntype = "INT"
        elif line[columns["Typ transakce"]].startswith("Záporný úrok"):
            StatementLine.trntype = "INT"
        elif line[columns["Typ transakce"]].startswith("Inkaso"):
            StatementLine.trntype = "DIRECTDEBIT"
        elif line[columns["Typ transakce"]].startswith("Srážka daně"):
            StatementLine.trntype = "DEBIT"
        elif line[columns["Typ transakce"]].startswith("Daň z úroků"):
            StatementLine.trntype = "DEBIT"
        elif line[columns["Typ transakce"]].startswith("Správa účtu"):
            StatementLine.trntype = "FEE"
        elif line[columns["Typ transakce"]].startswith("Jiný trans."):
            StatementLine.trntype = "FEE"
        elif line[columns["Typ transakce"]].startswith("Správa účtu"):
            StatementLine.trntype = "FEE"
        elif line[columns["Typ transakce"]].startswith("Poplatek"):
            StatementLine.trntype = "FEE"
        elif line[columns["Typ transakce"]].startswith("Směna"):
            StatementLine.trntype = "FEE"
        elif line[columns["Typ transakce"]].startswith("Zpráva"):
            StatementLine.trntype = "FEE"

        # Add payee's account number to payee field
        StatementLine.payee = StatementLine.payee + "|" + line[columns["Číslo protiúčtu"]]
        StatementLine.payee = StatementLine.payee.strip("|")

        # Add payment symbols to memo field
        if line[columns["Poznámka"]] != "" and line[columns["Poznámka"]] != StatementLine.memo:
            StatementLine.memo = StatementLine.memo + ", " + line[columns["Poznámka"]]
            StatementLine.memo = StatementLine.memo.strip(", ")

        if line[columns["VS"]] != "":
            StatementLine.memo = StatementLine.memo + "|VS:" + line[columns["VS"]]
        if line[columns["KS"]] != "":
            StatementLine.memo = StatementLine.memo + "|KS:" + line[columns["KS"]]
        if line[columns["SS"]] != "":
            StatementLine.memo = StatementLine.memo + "|SS:" + line[columns["SS"]]

        StatementLine.memo = StatementLine.memo.strip("|")

        # Raiffeisen may show various fees on the same line as the underlying transaction.
        # In case there is a fee connected with the transaction, the fee is added as different transaction

        # It may include thousands separators
        # ToDo: re-use parse_float (how??)
        line[columns["Poplatek"]] = re.sub(",", ".", line[columns["Poplatek"]])
        line[columns["Poplatek"]] = re.sub("[ a-zA-Z]", "", line[columns["Poplatek"]])

        # Some type of fee is standalone, not related to transaction amount. Add it to amount field only
        if float(line[columns["Poplatek"]]) != 0 and StatementLine.amount == 0:
            StatementLine.amount = float(line[columns["Poplatek"]])

        # Duplicate the current line and replace .amount with the fee amount ["Poplatek"]
        elif float(line[columns["Poplatek"]]) != 0 and StatementLine.amount != 0:
            fee_line = line[:]
            fee_line[columns["Zaúčtovaná částka"]] = line[columns["Poplatek"]]
            fee_line[columns["Poplatek"]] = ""
            fee_line[columns["Typ transakce"]] = "Poplatek"
            fee_line[columns["Zpráva"]] = "Poplatek: " + fee_line[columns["Zpráva"]]

            # Parse the newly generated fee_line and append it to the rest of the statements
            stmt_line = self.parse_record(fee_line)
            if stmt_line:
                stmt_line.assert_valid()
                self.statement.lines.append(stmt_line)

        if StatementLine.amount == 0:
            return None

        return StatementLine

    # The numbers in CSV may include some non-numerical chars, remove them.
    def parse_float(self, value):
        value = re.sub(",", ".", value)
        value = re.sub("[ a-zA-Z]", "", value)
        return super(RaiffeisenCZParser, self).parse_float(value)
