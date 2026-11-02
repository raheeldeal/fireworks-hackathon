#!/usr/bin/env python3
"""Generate prompts/*.txt from labels.json (and data/train.jsonl for few-shot). Deterministic."""
import json, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(HERE, "labels.json")))
label_block = "\n".join(f"- {k}: {v}" for k, v in L.items())

HEAD = ("You classify customer messages sent to a digital bank's support chat into exactly one intent.\n"
        "Choose from these 77 intents (label: meaning):\n\n" + label_block + "\n\n")

PLAIN = HEAD + "Reply with only the intent label, exactly as written above, nothing else."

CONF = HEAD + ("Reply with a single JSON object and nothing else:\n"
               '{"intent": "<one label exactly as written above>", "confidence": <number 0 to 1>}\n'
               "confidence is your honest probability that the intent is correct. Use values below 0.6 when two or more "
               "intents fit about equally.")

RULES = """
Disambiguation rules (learned from errors):
- "Where is my card / has not arrived" = card_arrival. "How long does delivery take / when will it ship" = card_delivery_estimate.
- A transfer the customer SENT that the recipient has not got = transfer_not_received_by_recipient. A transfer still processing from the sender's view, no recipient mentioned = pending_transfer. Asking how long transfers take in general = transfer_timing. Money sent TO the customer's account from another bank that has not shown = balance_not_updated_after_bank_transfer.
- A top-up that is slow = pending_top_up; a top-up that definitely did not go through = top_up_failed; a top-up that went through then came back = top_up_reverted.
- "I didn't make this card payment" = card_payment_not_recognised; "I didn't make this withdrawal" = cash_withdrawal_not_recognised; "I didn't set up this direct debit" = direct_debit_payment_not_recognised; "my card details were stolen / someone used my card" = compromised_card; "I lost my card" = lost_or_stolen_card.
- Wants money back from a merchant = request_refund; refund was promised but not visible = Refund_not_showing_up; a payment they made disappeared / was reversed on its own = reverted_card_payment?.
- Fee questions: fee on a card purchase = card_payment_fee_charged; fee on a transfer = transfer_fee_charged; fee on an ATM withdrawal = cash_withdrawal_charge; fee on currency exchange = exchange_charge; fee on a card top-up = top_up_by_card_charge; fee on a bank-transfer top-up = top_up_by_bank_transfer_charge; any other unexplained fee = extra_charge_on_statement.
- Wrong rate on a card purchase abroad = card_payment_wrong_exchange_rate; wrong rate on an ATM withdrawal abroad = wrong_exchange_rate_for_cash_withdrawal; asking what rate is used = exchange_rate.
- Identity: "why do you need to verify me" = why_verify_identity; "how do I verify / what do you need" = verify_my_identity; "verification keeps failing" = unable_to_verify_identity; asked where money came from = verify_source_of_funds; verifying a top-up card = verify_top_up.
- Cards: "how do I get a physical card" = get_physical_card; "order (another) physical card, cost of ordering" = order_physical_card; a second card for the same account = getting_spare_card; a virtual card = getting_virtual_card; a one-time/disposable card = get_disposable_virtual_card; limits on disposable cards = disposable_card_limits.
- "Which countries can I use it in / do you support my country" = country_support; "which currencies can I hold" = fiat_currency_support; "which cards/currencies can I top up with" = supported_cards_and_currencies; "Visa or Mastercard?" = visa_or_mastercard; "where is the card accepted" = card_acceptance.
- PIN: forgot app passcode = passcode_forgotten; PIN blocked after wrong tries = pin_blocked; want a new PIN = change_pin.
- Declines: card payment declined = declined_card_payment; ATM withdrawal declined = declined_cash_withdrawal; transfer declined = declined_transfer; card not working with no specific decline described = card_not_working; tap not working = contactless_not_working; virtual card not working = virtual_card_not_working.
"""

RUBRIC = HEAD + RULES.strip() + "\n\n" + ("Reply with a single JSON object and nothing else:\n"
               '{"intent": "<one label exactly as written above>", "confidence": <number 0 to 1>}\n'
               "confidence is your honest probability that the intent is correct. Use values below 0.6 when two or more "
               "intents fit about equally.")

# 5-shot: pick 5 train examples from intents that are commonly confused (deterministic)
train = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl"))]
want = ["transfer_not_received_by_recipient", "pending_top_up", "card_delivery_estimate", "request_refund", "why_verify_identity"]
rng = random.Random(1)
shots = []
for w in want:
    cands = [t for t in train if t["label"] == w]
    shots.append(rng.choice(cands))
shot_block = "\n".join(f'Message: {s["text"]}\nAnswer: {{"intent": "{s["label"]}", "confidence": 0.9}}' for s in shots)
FEWSHOT = RUBRIC + "\n\nExamples:\n" + shot_block

os.makedirs(os.path.join(HERE, "prompts"), exist_ok=True)
for name, txt in [("v1_plain", PLAIN), ("v2_conf", CONF), ("v3_rubric", RUBRIC), ("v4_fewshot", FEWSHOT)]:
    open(os.path.join(HERE, "prompts", f"{name}.txt"), "w").write(txt)
    print(name, len(txt), "chars ~", len(txt) // 4, "tokens")
json.dump(shots, open(os.path.join(HERE, "prompts", "fewshot_examples.json"), "w"), indent=1)
