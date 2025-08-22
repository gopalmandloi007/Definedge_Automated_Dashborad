class ConnectToIntegrate:
    def login(self, *args, **kwargs):
        pass
    def set_session_keys(self, *args, **kwargs):
        pass

class IntegrateOrders:
    def __init__(self, conn):
        self.conn = conn
    def holdings(self):
        # Dummy data for testing
        return {"data": [{"dp_qty": 10, "avg_buy_price": 100, "tradingsymbol": [{"exchange": "NSE", "tradingsymbol": "SBIN", "token": "123", "isin": "IN1234567890"}]}]}

