"""Signature-return state, separate from approval of numerical scores."""
from .aggregate_scores import confirmation_status

# Original four-form signed returns verified during the 2026-11-18 paper import.
# Older imports omitted per-form coverage; unfamiliar imports do not inherit it.
VERIFIED_FOUR_FORM_RETURNS = frozenset({
    'c386d38581bbc9404af9c287398de1ff3f6af2d7bfc1504684383fe927644138',
    'fa41a320b9a5ccc6605b2786b2ff125d987db0fdc5d4fd93e74cad9985c75bb3',
    'cacd8e93e9d07fe3a8651fdf754d8ca77714b98250c4469c7769e97a40a9d654',
})


def completed(data):
    if confirmation_status(data) != 'CONFIRMED':
        return False
    confirmation = data['score_confirmation']
    if confirmation.get('pending_signatures'):
        return False
    source = confirmation.get('file', {})
    for receipt in data.get('signed_receipts', []):
        file = receipt.get('file', {})
        if file.get('id') != source.get('id') or file.get('sha256') != source.get('sha256'):
            continue
        if receipt.get('pending_signatures'):
            continue
        forms = receipt.get('site_manager_signed_forms', receipt.get('signed_forms', []))
        if set(forms) >= {'report', 'law', 'manager', 'supervisor'}:
            return True
        if (receipt.get('source_kind') == 'SIGNED_PAPER_EVALUATION'
                and file.get('sha256') in VERIFIED_FOUR_FORM_RETURNS):
            return True
    return False
