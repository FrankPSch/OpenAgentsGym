from AlgorithmImports import *


class EmaCrossSpy(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_end_date(2025, 12, 31)
        self._symbol = self.add_equity("SPY", Resolution.DAILY).symbol
        self._fast = self.ema(self._symbol, 5, Resolution.DAILY)
        self._slow = self.ema(self._symbol, 160, Resolution.DAILY)
        self.set_warm_up(320, Resolution.DAILY)

    def on_data(self, data):
        if self.is_warming_up or not self._slow.is_ready:
            return
        if self._fast.current.value > self._slow.current.value:
            self.set_holdings(self._symbol, 1)
        elif self.portfolio[self._symbol].invested:
            self.liquidate(self._symbol)
