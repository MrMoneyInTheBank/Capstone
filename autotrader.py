import asyncio
import itertools
import math as mt
from typing import List

from ready_trader_go import BaseAutoTrader, Instrument, Lifespan, MAXIMUM_ASK, MINIMUM_BID, Side


LOT_SIZE = 10
POSITION_LIMIT = 100
FUTURE_LIMIT = 100
TICK_SIZE_IN_CENTS = 100
MIN_BID_NEAREST_TICK = (
    MINIMUM_BID + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
MAX_ASK_NEAREST_TICK = MAXIMUM_ASK // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS


class AutoTrader(BaseAutoTrader):

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise a new instance of the AutoTrader class."""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0

        self.moving_avg_50 = 0
        self.volatility_50 = 0
        self.etf_price = 0
        self.future_price = 0
        self.spread_ratio = 0
        self.ratios = []
        self.count = 0
        self.window = 50
        self.future_position = 0

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s",
                            client_order_id, error_message.decode())
        if client_order_id != 0 and (client_order_id in self.bids or client_order_id in self.asks):
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_hedge_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your hedge orders is filled.

        The price is the average price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received hedge filled for order %d with average price %d and volume %d", client_order_id,
                         price, volume)

    def moving_average(self) -> float:
        """Returns the average of the last 50 prices
        """

        total = 0
        for i in range(self.count - self.window, self.count - 1):
            total += self.ratios[i]

        return total / self.window

    def volatility(self) -> float:
        """Returns the standard deviation of the last 50 prices
        """

        total = 0
        for i in range(self.count - self.window, self.count-1):
            total += (self.ratios[i] - self.moving_avg_50) ** 2

        return mt.sqrt(total / (self.window - 1))

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        self.logger.info("received order book for instrument %d with sequence number %d", instrument,
                         sequence_number)

        # Updating the latest future price
        if instrument == Instrument.FUTURE:
            self.future_price = (bid_prices[0] + ask_prices[0]) / 2
            if self.etf_price == 0:
                return

        # Updating the latest ETF price
        if instrument == Instrument.ETF:
            self.etf_price = (bid_prices[0] + ask_prices[0]) / 2
            if self.future_price == 0:
                return

        # Calculating the spread ratio and adding it to the list
        self.spread_ratio = self.etf_price / self.future_price
        self.ratios.append(self.spread_ratio)

        # if we have enough data, we can look for trading opportunities
        if self.count >= self.window:

            # normalizing the data
            self.moving_avg_50 = self.moving_average()
            self.volatility_50 = self.volatility()
            norm_spread = (self.spread_ratio -
                           self.moving_avg_50) / self.volatility_50

            new_bid_price = bid_prices[0] if bid_prices[0] != 0 else 0
            new_ask_price = ask_prices[0] if ask_prices[0] != 0 else 0

            # converting the bid and ask prices to tick size multiples
            new_bid_price = (
                new_bid_price + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
            new_ask_price = new_ask_price // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS

            # if bid or ask price is invalid, we discard the previously entered trade
            if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0
                return
            if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0
                return

            # If ETF is overbought relative to the future, we short the ETF and long the future
            if norm_spread > 1.5:
                if self.ask_id == 0 and new_ask_price != 0 and self.position - LOT_SIZE > -POSITION_LIMIT and self.future_position + LOT_SIZE < FUTURE_LIMIT:
                    self.ask_id = next(self.order_ids)
                    self.ask_price = new_ask_price
                    self.send_insert_order(
                        self.ask_id, Side.SELL, new_ask_price, LOT_SIZE, Lifespan.FILL_AND_KILL)
                    self.asks.add(self.ask_id)
            # If future is overbought relative to the ETF, we short the future and long the ETF
            elif norm_spread < 0.95:
                if self.bid_id == 0 and new_ask_price != 0 and self.position + LOT_SIZE < POSITION_LIMIT and self.future_position - LOT_SIZE > -FUTURE_LIMIT:
                    self.bid_id = next(self.order_ids)
                    self.bid_price = new_bid_price
                    self.send_insert_order(
                        self.bid_id, Side.BUY, new_bid_price, LOT_SIZE, Lifespan.FILL_AND_KILL)
                    self.bids.add(self.bid_id)

        self.count += 1

    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received order filled for order %d with price %d and volume %d", client_order_id,
                         price, volume)
        if client_order_id in self.bids:
            self.position += volume
            self.send_hedge_order(next(self.order_ids),
                                  Side.ASK, MIN_BID_NEAREST_TICK, volume)
            # This is here to make sure that we don't breach the future limit
            self.future_position -= volume
        elif client_order_id in self.asks:
            self.position -= volume
            self.send_hedge_order(next(self.order_ids),
                                  Side.BID, MAX_ASK_NEAREST_TICK, volume)
            # This is here to make sure that we don't breach the future limit
            self.future_position += volume

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int,
                                fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        self.logger.info("received order status for order %d with fill volume %d remaining %d and fees %d",
                         client_order_id, fill_volume, remaining_volume, fees)
        if remaining_volume == 0:
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0

            # It could be either a bid or an ask
            self.bids.discard(client_order_id)
            self.asks.discard(client_order_id)

    def on_trade_ticks_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                               ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically when there is trading activity on the market.

        The five best ask (i.e. sell) and bid (i.e. buy) prices at which there
        has been trading activity are reported along with the aggregated volume
        traded at each of those price levels.

        If there are less than five prices on a side, then zeros will appear at
        the end of both the prices and volumes arrays.
        """
        self.logger.info("received trade ticks for instrument %d with sequence number %d", instrument,
                         sequence_number)
