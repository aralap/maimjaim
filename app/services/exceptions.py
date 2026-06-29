class InventoryError(Exception):
    """Base inventory error."""


class InsufficientStockError(InventoryError):
    def __init__(self, variant_id: int, requested: int, available: int):
        self.variant_id = variant_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuficiente para la variante {variant_id}: "
            f"solicitado {requested}, disponible {available}"
        )


class OrderError(Exception):
    """Base order error."""


class InvalidOrderStateError(OrderError):
    ACTION_LABELS = {
        "confirm": "confirmar",
        "fulfill": "entregar",
        "cancel": "cancelar",
    }

    def __init__(self, order_id: int, current_status: str, action: str):
        self.order_id = order_id
        self.current_status = current_status
        self.action = action
        action_label = self.ACTION_LABELS.get(action, action)
        super().__init__(
            f"No se puede {action_label} el pedido {order_id} en estado '{current_status}'"
        )
