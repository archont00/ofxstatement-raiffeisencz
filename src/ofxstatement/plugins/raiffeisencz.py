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
        # .csvfile is a work-around and is used for exporting fees to a new CSV file
        RaiffeisenCZPlugin.csvfile = re.sub(".csv", "", filename) + "-fees.csv"

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
    date_format = "%d.%m.%Y"

    # The columns are:
    #  0 Datum provedení
    #  1 Datum zaúčtování
    #  2 Číslo účtu
    #  3 Název účtu
    #  4 Kategorie transakce
    #  5 Číslo protiúčtu
    #  6 Název protiúčtu
    #  7 Typ transakce
    #  8 Zpráva
    #  9 Poznámka
    # 10 Variabilní sym
    # 11 Konstantní symbol
    # 12 Specifický symbol
    # 13 Zaúčtovaná částka
    # 14 Měna účtu
    # 15 Původní částka a měna
    # 16 Původní částka a měna (2)
    # 17 Poplatek
    # 18 Id transakce

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.columns = None
        self.mappings = None

    mappings = {"date_user": 0,
                "date": 1,
                "memo": 9,
                "payee": 6,
                "amount": 13,
                "check_no": 10,
                "refnum": 18, }

    def split_records(self):
        return csv.reader(self.fin, delimiter=';', quotechar='"')

    def parse_record(self, line):
        """Parse given transaction line and return StatementLine object
        """

        # First line of CSV file contains headers, not an actual transaction
        if self.cur_record == 1:
            # Create a heading line for the -fees.csv file
            with open(RaiffeisenCZPlugin.csvfile, "w", encoding=RaiffeisenCZPlugin.encoding) as output:
                writer = csv.writer(output, lineterminator='\n', delimiter=';', quotechar='"')
                writer.writerow(line)
                output.close()

            # Prepare columns headers lookup table for parsing
            # v ... column heading
            # i ... column index (expected by .mappings)
            self.columns = {v: i for i,v in enumerate(line)}
            self.mappings = {
                "date":      self.columns['Datum zaúčtování'],
                "date_user": self.columns['Datum provedení'],
                "memo":      self.columns['Poznámka'],
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

        StatementLine.date_user = datetime.strptime(StatementLine.date_user, self.date_format)

        StatementLine.id = statement.generate_transaction_id(StatementLine)

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

        # .payee becomes OFX.NAME which becomes "Description" in GnuCash
        # .memo  becomes OFX.MEMO which becomes "Notes"       in GnuCash
        # When payee is empty, GnuCash imports .memo to "Description" and keeps "Notes" empty

        # Add payee's account number to payee field
        if line[columns["Číslo protiúčtu"]] != "":
            StatementLine.payee = StatementLine.payee + "|ÚČ: " + line[columns["Číslo protiúčtu"]]

        # Add payment symbols to memo field
        if line[columns["VS"]] != "":
            StatementLine.memo = StatementLine.memo + "|VS: " + line[columns["VS"]]
        if line[columns["KS"]] != "":
            StatementLine.memo = StatementLine.memo + "|KS: " + line[columns["KS"]]
        if line[columns["SS"]] != "":
            StatementLine.memo = StatementLine.memo + "|SS: " + line[columns["SS"]]

        # Raiffeisen may show various fees on the same line  as the underlying transaction
        # For now, we simply create a new CSV file with the fee amount moved to line[13].
        # This needs to be processed again manually:
        # $ ofxstatement convert -t raiffeisencz in-fees.csv out-fees.ofx

        # It may include thousands separators
        # ToDo: re-use parse_float (how??)
        line[columns["Poplatek"]] = re.sub(",", ".", line[columns["Poplatek"]])
        line[columns["Poplatek"]] = re.sub("[ a-zA-Z]", "", line[columns["Poplatek"]])

        # No need to duplicate a line if StatementLine.amount is zero and only a fee exists
        if float(line[columns["Poplatek"]]) != 0 and StatementLine.amount == 0:
            StatementLine.amount = float(line[columns["Poplatek"]])

        # Duplicate the current line and replace amount [13] with the fee amount [17]
        if float(line[columns["Poplatek"]]) != 0 and StatementLine.amount != 0:
            exportline = line[:]
            exportline[columns["Zaúčtovaná částka"]] = line[columns["Poplatek"]]
            exportline[columns["Poplatek"]] = ''
            exportline[columns["Typ transakce"]] = "Poplatek"
            exportline[columns["Poznámka"]] = "Poplatek: " + exportline[columns["Poznámka"]]

            with open(RaiffeisenCZPlugin.csvfile, "a", encoding=RaiffeisenCZPlugin.encoding) as output:
                writer = csv.writer(output, lineterminator='\n', delimiter=';', quotechar='"')
                writer.writerow(exportline)

        if StatementLine.amount == 0:
            return None

        return StatementLine

    # The exported numbers may include some non-numerical chars, remove them.
    def parse_float(self, value):
        value = re.sub(",", ".", value)
        value = re.sub("[ a-zA-Z]", "", value)
        return super(RaiffeisenCZParser, self).parse_float(value)
