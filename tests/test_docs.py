"""Documentation links must work in the shipped tree, including merged-page anchors."""
from pathlib import Path
import tempfile
import unittest

from tools.check_docs import anchors, check_documents


class DocumentationTests(unittest.TestCase):
    def test_relative_unicode_and_duplicate_heading_links_work_after_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            guide = root / "docs/guides/guide.md"
            reference = root / "docs/reference/contract.md"
            guide.parent.mkdir(parents=True)
            reference.parent.mkdir(parents=True)
            guide.write_text('[契約](../reference/contract.md#%E8%B3%87%E6%96%99-1)\n'
                             '[Repeat](../reference/contract.md#repeat-1)\n', encoding="utf-8")
            reference.write_text('# Contract\n## 資料\n## 資料\n## Repeat\n## Repeat\n', encoding="utf-8")
            self.assertEqual(check_documents(root, [guide, reference]), (2, 2, []))

    def test_existing_unshipped_document_and_missing_anchor_are_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            guide, private = root / "guide.md", root / "local.md"
            guide.write_text('# Guide\n[Local](local.md)\n[Old heading](#removed)\n', encoding="utf-8")
            private.write_text('# Private\n', encoding="utf-8")
            documents, links, errors = check_documents(root, [guide])
            self.assertEqual((documents, links), (1, 2))
            self.assertEqual(len(errors), 2)
            self.assertIn('not in the reviewed source', errors[0])
            self.assertIn('missing heading anchor', errors[1])

    def test_fenced_examples_do_not_create_headings_and_explicit_anchors_are_supported(self):
        self.assertEqual(anchors('# Page\n```sh\n## example\n```\n'
                                 '<a id="legacy-anchor"></a>\n## Real `code` &amp; text\n'),
                         {'page', 'legacy-anchor', 'real-code--text'})


if __name__ == '__main__':
    unittest.main()
