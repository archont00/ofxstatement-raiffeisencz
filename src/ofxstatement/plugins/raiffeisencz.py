import csv
from datetime import datetime
import re

from ofxstatement import statement
from ofxstatement.parser import CsvStatementParser
from ofxstatement.plugin import Plugin
from ofxstatement.statement import Statement


class RaiffeisenCZPlugin(Plugin):
    """RaiffeisenCZ plugin
    """

    def get_parser(self, filename):
        RaiffeisenCZPlugin.filename = filename
        encoding = self.settings.get('charset', 'cp1250')
        f = open(filename, "r", encoding=encoding)
        parser = RaiffeisenCZParser(f)
        parser.statement.currency = self.settings.get('currency', 'CZK')
        parser.statement.bank_id = self.settings.get('bank', 'RZBCCZPP')
        parser.statement.account_id = self.settings.get('account', '')
        parser.statement.account_type = self.settings.get('account_type', 'CHECKING')
        parser.statement.trntype = "OTHER"
        # parser.swap_payee_and_memo = self.settings.get('swap-payee-and-memo', True)
        return parser


class RaiffeisenCZParser(CsvStatementParser):
    mappings = {"date_user": 0,
                "date": 5,
                "memo": 2,
                "payee": 3,
                "amount": 12,
                "check_no": 9,
                "refnum": 8, }

    date_format = "%d.%m.%Y"

    def split_records(self):
        return csv.reader(self.fin, delimiter=';', quotechar='"')

    def parse_record(self, line):
        if self.cur_record == 1:
            return None

        if line[12] == '':
            line[12] = "0"

        if line[13] == '':
            line[13] = "0"

        if line[14] == '':
            line[14] = "0"

        if line[15] == '':
            line[15] = "0"

        sl = super(RaiffeisenCZParser, self).parse_record(line)
        sl.date_user = datetime.strptime(sl.date_user, self.date_format)

        sl.id = statement.generate_transaction_id(sl)

        if line[7].startswith("Převod"):
            sl.trntype = "XFER"
        if line[7].startswith("Příchozí platba"):
            sl.trntype = "CREDIT"
        if line[7].startswith("Trvalý převod"):
            sl.trntype = "REPEATPMT"
        if line[7].startswith("Kladný úrok"):
            sl.trntype = "INT"
        if line[7].startswith("Záporný úrok"):
            sl.trntype = "INT"
        if line[7].startswith("Inkaso"):
            sl.trntype = "DIRECTDEBIT"
        if line[7].startswith("Srážka daně"):
            sl.trntype = "DEBIT"
        if line[7].startswith("Správa účtu"):
            sl.trntype = "FEE"
        if line[7].startswith("Jiný trans."):
            sl.trntype = "FEE"
        if line[7].startswith("Správa účtu"):
            sl.trntype = "FEE"
        if line[7].startswith("Poplatek"):
            sl.trntype = "FEE"
        if line[7].startswith("Směna"):
            sl.trntype = "FEE"
        if line[7].startswith("Zpráva"):
            sl.trntype = "FEE"

        # Raiffeisen may show various fees on the same line  as the underlying transaction
        # For now, we simply create a new modified CSV file with the fee moved to line[12]
        # This needs to be processed again manually by 'ofxstatement convert raiffeisencz'
        for x in range(13, 16):
            # ToDo: re-use parse_float (how??)
            val1 = re.sub(",", ".", line[x])
            val1 = re.sub("[ a-zA-Z]", "", val1)

            if float(val1) != 0:
                exportline = line[:]
                exportline[12] = line[x]

                if x == 13:
                    exportline[7] = "Poplatek"
                if x == 14:
                    exportline[7] = "Směna"
                if x == 15:
                    exportline[7] = "Zpráva"

                for y in range(13, 16):
                    exportline[y] = ''

                csvfile = re.sub(".csv", "", RaiffeisenCZPlugin.filename) + "-fees-to-be-processed-separately.csv"
                with open(csvfile, "a") as output:
                    writer = csv.writer(output, lineterminator='\n')
                    writer.writerow(exportline)

            # ToDo: instead of exporting the above to CSV, try to add the exportline to
            #       the end of statement (from imported input.csv).

        return sl


    def parse_float(self, value):
        value = re.sub(",", ".", value)
        value = re.sub("[ a-zA-Z]", "", value)
        return super(RaiffeisenCZParser, self).parse_float(value)
