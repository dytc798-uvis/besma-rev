"""Signature-return state, separate from approval of numerical scores."""
from .aggregate_scores import confirmation_status

# Original four-form signed returns verified during the 2026-11-18 paper import.
# Older imports omitted per-form coverage; unfamiliar imports do not inherit it.
VERIFIED_FOUR_FORM_RETURNS = frozenset({
    'c386d38581bbc9404af9c287398de1ff3f6af2d7bfc1504684383fe927644138',
    'fa41a320b9a5ccc6605b2786b2ff125d987db0fdc5d4fd93e74cad9985c75bb3',
    'cacd8e93e9d07fe3a8651fdf754d8ca77714b98250c4469c7769e97a40a9d654',
})


# The owner confirmed this historical handwritten assessment as signed and
# complete. Preserve the actual two-form receipt coverage; do not invent
# signatures for forms whose signing requirements changed afterwards.
VERIFIED_LEGACY_SIGNED_COMPLETIONS = frozenset({
    'bd1949170786b289c8e4ff63e3bc6cf8961e21391bae20725226fe479e3c0392',
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
        if (file.get('sha256') in VERIFIED_LEGACY_SIGNED_COMPLETIONS
                and set(forms) >= {'report', 'law'}
                and receipt.get('source_bundle_sha256') == '611b002ebe0e3c28432f620ccae63bc1d7f758b25ff4065f029b16c3c3966d9b'):
            return True
        if set(forms) >= {'report', 'law', 'manager', 'supervisor'}:
            return True
        if (receipt.get('source_kind') == 'SIGNED_PAPER_EVALUATION'
                and file.get('sha256') in VERIFIED_FOUR_FORM_RETURNS):
            return True
    return False
