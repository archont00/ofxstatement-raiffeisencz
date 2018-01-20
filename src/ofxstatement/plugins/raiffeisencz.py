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

    mappings = {"date_user": 0,
                "date": 1,
                "memo": 9,
                "payee": 6,
                "amount": 13,
                "check_no": 10,
                "refnum": 18, }

    date_format = "%d.%m.%Y"

    def split_records(self):
        return csv.reader(self.fin, delimiter=';', quotechar='"')

    def parse_record(self, line):
        if self.cur_record == 1:
            # Create a heading line for the -fees.csv file
            with open(RaiffeisenCZPlugin.csvfile, "w", encoding=RaiffeisenCZPlugin.encoding) as output:
                writer = csv.writer(output, lineterminator='\n', delimiter=';', quotechar='"')
                writer.writerow(line)
                output.close()
            # And skip further processing by parser
            return None

        if line[13] == '':
            line[13] = "0"

        if line[17] == '':
            line[17] = "0"

        sl = super(RaiffeisenCZParser, self).parse_record(line)
        sl.date_user = datetime.strptime(sl.date_user, self.date_format)

        sl.id = statement.generate_transaction_id(sl)

        if line[7].startswith("Převod"):
            sl.trntype = "XFER"
        elif line[7].startswith("Platba"):
            sl.trntype = "XFER"
        elif line[7].startswith("Jednorázová platba"):
            sl.trntype = "XFER"
        elif line[7].startswith("Příchozí platba"):
            sl.trntype = "CREDIT"
        elif line[7].startswith("Trvalý převod"):
            sl.trntype = "REPEATPMT"
        elif line[7].startswith("Trvalá platba"):
            sl.trntype = "REPEATPMT"
        elif line[7].startswith("Kladný úrok"):
            sl.trntype = "INT"
        elif line[7].startswith("Záporný úrok"):
            sl.trntype = "INT"
        elif line[7].startswith("Inkaso"):
            sl.trntype = "DIRECTDEBIT"
        elif line[7].startswith("Srážka daně"):
            sl.trntype = "DEBIT"
        elif line[7].startswith("Daň z úroků"):
            sl.trntype = "DEBIT"
        elif line[7].startswith("Správa účtu"):
            sl.trntype = "FEE"
        elif line[7].startswith("Jiný trans."):
            sl.trntype = "FEE"
        elif line[7].startswith("Správa účtu"):
            sl.trntype = "FEE"
        elif line[7].startswith("Poplatek"):
            sl.trntype = "FEE"
        elif line[7].startswith("Směna"):
            sl.trntype = "FEE"
        elif line[7].startswith("Zpráva"):
            sl.trntype = "FEE"

        # .payee becomes OFX.NAME which becomes "Description" in GnuCash
        # .memo  becomes OFX.MEMO which becomes "Notes"       in GnuCash
        # When payee is empty, GnuCash imports .memo to "Description" and keeps "Notes" empty
        if not (line[6] == '' or line[6] == ' '):
            sl.payee = sl.payee + "|ÚČ: " + line[6]
        if not (line[10] == '' or line[10] == ' '):
            sl.memo = sl.memo + "|VS: " + line[10]
        if not (line[11] == '' or line[11] == ' '):
            sl.memo = sl.memo + "|KS: " + line[11]
        if not (line[12] == '' or line[12] == ' '):
            sl.memo = sl.memo + "|SS: " + line[12]

        # Raiffeisen may show various fees on the same line  as the underlying transaction
        # For now, we simply create a new CSV file with the fee amount moved to line[13].
        # This needs to be processed again manually:
        # $ ofxstatement convert -t raiffeisencz in-fees.csv out-fees.ofx

        # It may include thousands separators
        # ToDo: re-use parse_float (how??)
        line[17] = re.sub(",", ".", line[17])
        line[17] = re.sub("[ a-zA-Z]", "", line[17])

        # No need to duplicate a line if sl.amount is zero and only a fee exists
        if float(line[17]) != 0 and sl.amount == 0:
            sl.amount = float(line[17])

        # Duplicate the current line and replace amount [13] with the fee amount [17]
        if float(line[17]) != 0 and sl.amount != 0:
            exportline = line[:]
            exportline[13] = line[17]
            exportline[17] = ''
            exportline[7] = "Poplatek"
            exportline[9] = "Poplatek" + exportline[9]

            with open(RaiffeisenCZPlugin.csvfile, "a", encoding=RaiffeisenCZPlugin.encoding) as output:
                writer = csv.writer(output, lineterminator='\n', delimiter=';', quotechar='"')
                writer.writerow(exportline)

        if sl.amount == 0:
            return None

        return sl

    # The exported numbers may include some non-numerical chars, remove them.
    def parse_float(self, value):
        value = re.sub(",", ".", value)
        value = re.sub("[ a-zA-Z]", "", value)
        return super(RaiffeisenCZParser, self).parse_float(value)
