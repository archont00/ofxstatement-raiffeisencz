This is a parser for CSV statements produced by Raiffeisen bank a.s.
(Czech Republic) from within the report in Account History // Account
Movements.

It is a plugin for `ofxstatement`_.

.. _ofxstatement: https://github.com/kedder/ofxstatement

Usage:
    ofxstatement convert raiffeisencz bank-statement.csv bank-statement.qfx


ToDo:

* There may be up to 3 types of fees shown on the same line of the
  statement as the underlying transaction. Currently this is not
  dealt with properly, instead a new CSV file is generated (with
  suffix "-fees-to-be-processed-separately.csv") and the user must
  run ofxstatement with this file again to get another OFX file.
