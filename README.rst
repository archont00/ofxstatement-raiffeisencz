This is a parser for CSV statements produced by Raiffeisenbank, a.s.
(Czech Republic) from within the report in Account History // Account
Movements.

It is a plugin for `ofxstatement`_.

.. _ofxstatement: https://github.com/kedder/ofxstatement

Usage
=====
::

  $ ofxstatement convert -t raiffeisencz bank-statement.csv bank-statement.ofx
  $ ofxstatement convert -t raiffeisencz:EUR bank-statement.csv bank-statement.ofx

Configuration
=============

To edit the configuration file run::
  $ ofxstatement edit-config

and set e.g. the following::

  [raiffeisencz]
  plugin = raiffeisencz
  currency = CZK
  account = RB CA

  [raiffeisencz:EUR]
  plugin = raiffeisencz
  currency = EUR
  account = RB CA EUR
