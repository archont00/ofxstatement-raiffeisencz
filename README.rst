This is a parser for CSV statements produced by Raiffeisenbank, a.s.
(Czech Republic) from within the report in Account History // Account
Movements.

It is a plugin for `ofxstatement`_.

.. _ofxstatement: https://github.com/kedder/ofxstatement

Usage:

    ofxstatement convert -t raiffeisencz bank-statement.csv bank-statement.ofx

    ofxstatement convert -t raiffeisencz:EUR bank-statement.csv bank-statement.ofx

Configuration:

    ofxstatement edit-config

and set e.g. the following

    [raiffeisencz:EUR]

    plugin = raiffeisencz

    currency = EUR

    account = RB CA



ToDo:

* There may be up to 3 types of fees shown on the same line of the
  statement as the underlying transaction. Currently this is not
  dealt with properly, instead a new CSV file is generated (with
  suffix "-fees.csv") and the user must run ofxstatement with this
  file again to get another OFX file.
  See 'tools/mk_bank-rb.sh' for example of a shell script to automate
  the process.
