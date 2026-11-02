import copy
import unittest

from app.modules.monthly_collection.source_quality import notes_by_id


class ReviewedSourceQualityTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(id='a'*64, sha256='b'*64, size=10, category='risk', month='2026-11', filename='평가.pdf')

    def decode(self, note, row=None):
        return notes_by_id({'items': [row or self.row], 'reviewed_source_notes': [note]})

    def note(self, kind, **values):
        return dict(id=self.row['id'], sha256=self.row['sha256'], kind=kind, **values)

    def test_invalid_calendar_date_is_specific_and_does_not_change_receipt(self):
        before = copy.deepcopy(self.row)
        result = self.decode(self.note('INVALID_DATE', document_month='2026-11', day=31))
        self.assertEqual(result[self.row['id']], ['원문 날짜 확인: 2026.11.31은 존재하지 않는 날짜입니다.'])
        self.assertEqual(self.row, before)

    def test_leap_year_and_valid_month_end_are_not_false_warnings(self):
        for month, day in [('2024-02', 29), ('2026-10', 31), ('2026-11', 30)]:
            with self.subTest(month=month, day=day):
                self.assertEqual(self.decode(self.note('INVALID_DATE', document_month=month, day=day)), {})
        self.assertIn(self.row['id'], self.decode(self.note('INVALID_DATE', document_month='2025-02', day=29)))

    def test_table_month_does_not_claim_the_whole_document_is_from_that_month(self):
        result = self.decode(self.note('LABEL_MONTH', label_month=7))
        self.assertEqual(result[self.row['id']], ['원문 월 표기 확인: 표제 7월 / 등록 자료월 2026.11'])
        self.assertEqual(self.decode(self.note('LABEL_MONTH', label_month=11)), {})

    def test_wrong_file_or_revised_hash_does_not_inherit_a_warning(self):
        for field, value in [('id', 'c'*64), ('sha256', 'c'*64)]:
            note = self.note('INVALID_DATE', document_month='2026-11', day=31)
            note[field] = value
            self.assertEqual(self.decode(note), {})

    def test_untrusted_text_extra_fields_and_non_numeric_values_do_not_render(self):
        notes = [self.note('LABEL_MONTH', label_month=True), self.note('LABEL_MONTH', label_month='7'),
                 self.note('LABEL_MONTH', label_month=0), self.note('LABEL_MONTH', label_month=13),
                 self.note('INVALID_DATE', document_month='2026-13', day=31),
                 self.note('INVALID_DATE', document_month='2026-11', day=True),
                 self.note('INVALID_DATE', document_month='2026-11', day='31'),
                 self.note('INVALID_DATE', document_month='2026-11', day=32),
                 self.note('LABEL_MONTH', label_month=7, text='<script>unexpected</script>')]
        for note in notes:
            with self.subTest(note=note):
                self.assertEqual(self.decode(note), {})

    def test_existing_review_codes_and_duplicate_message_handling_are_preserved(self):
        notes = [self.note('PERIOD', document_month='2026-10'), self.note('PAGES', present=1, expected=2),
                 self.note('LABEL_MONTH', label_month=7), self.note('LABEL_MONTH', label_month=7)]
        result = notes_by_id({'items': [self.row], 'reviewed_source_notes': notes})
        self.assertEqual(result[self.row['id']], ['원문 날짜 확인: 2026.10 / 등록 자료월 2026.11',
            '원문 확인: PDF 1쪽 / 원문 표기 2쪽. 전체 자료 여부 확인 필요',
            '원문 월 표기 확인: 표제 7월 / 등록 자료월 2026.11'])

    def test_source_state_difference_is_factual_and_does_not_complete_an_action(self):
        row = dict(self.row, category='opinions')
        before = copy.deepcopy(row)
        result = self.decode(self.note('OPINION_STATE_DIFFERENCE'), row)
        self.assertEqual(result[row['id']], ['같은 의견의 원본별 조치상태가 다릅니다.'])
        self.assertEqual(row, before)

    def test_source_state_difference_is_limited_to_exact_opinion_bytes(self):
        note = self.note('OPINION_STATE_DIFFERENCE')
        self.assertEqual(self.decode(note), {})
        for row in [dict(self.row, category='opinions', id='c'*64),
                    dict(self.row, category='opinions', sha256='c'*64)]:
            self.assertEqual(self.decode(note, row), {})

    def test_source_state_difference_never_renders_supplied_body_or_person(self):
        for field in ['person', 'opinion', 'status', 'text']:
            self.assertEqual(self.decode(self.note('OPINION_STATE_DIFFERENCE', **{field: '<script>private</script>'}),
                                         dict(self.row, category='opinions')), {})

    def test_one_review_does_not_change_other_files_or_complete_anything(self):
        second = dict(self.row, id='c'*64, sha256='d'*64)
        value = {'items': [self.row, second], 'review_count': 121,
                 'reviewed_source_notes': [self.note('INVALID_DATE', document_month='2026-11', day=31)]}
        before = copy.deepcopy(value)
        result = notes_by_id(value)
        self.assertNotIn(second['id'], result)
        self.assertEqual(value, before)


if __name__ == '__main__':
    unittest.main()
