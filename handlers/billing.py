"""Balance gate shared by both handler surfaces (inline callbacks and text)."""

from keyboards import show_menu
from services import crud
from services import process


async def open_billing(message, telegram_id, cost):
    """Check the balance before a paid action.

    Returns a Billing to put the remaining gems into the footer, or None when
    the user cannot pay — then they get the price, their balance and the
    top-up buttons instead of content."""
    if cost <= 0:
        return process.Billing()
    balance = await crud.get_balance(telegram_id)
    if balance is None:          # user is not in the DB yet, do not block them
        return process.Billing()
    if balance < cost:
        await message.answer(process.not_enough_message(balance, cost),
                             parse_mode="Markdown", reply_markup=await show_menu('balance'))
        return None
    return process.Billing(balance=balance, cost=cost)
