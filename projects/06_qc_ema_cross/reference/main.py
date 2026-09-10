from AlgorithmImports import *


class EmaCrossSpy(QCAlgorithm):
    """EMA(5)/EMA(160) crossover on SPY, daily resolution, long-only."""

    def Initialize(self):
        self.SetStartDate(2024, 5, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(100000)
        self.symbol = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.fast = self.EMA(self.symbol, 5, Resolution.Daily)
        self.slow = self.EMA(self.symbol, 160, Resolution.Daily)
        self.SetWarmUp(160, Resolution.Daily)

    def OnData(self, data):
        if self.IsWarmingUp or not (self.fast.IsReady and self.slow.IsReady):
            return
        if not data.Bars.ContainsKey(self.symbol):
            return
        if self.fast.Current.Value > self.slow.Current.Value and not self.Portfolio.Invested:
            self.SetHoldings(self.symbol, 1.0)
        elif self.fast.Current.Value < self.slow.Current.Value and self.Portfolio.Invested:
            self.Liquidate(self.symbol)
