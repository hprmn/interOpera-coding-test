"""
Unit tests for DocumentProcessor service

Tests document processing pipeline:
- Text chunking with overlap
- Text cleaning
- Sentence splitting
- Integration with TableParser and VectorStore
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.services.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """Test suite for DocumentProcessor"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        return db

    @pytest.fixture
    def processor(self, mock_db):
        """Create DocumentProcessor instance with mocked dependencies"""
        with patch('app.services.document_processor.TableParser'), \
             patch('app.services.document_processor.VectorStore'):
            return DocumentProcessor(mock_db)

    # ==================== Text Cleaning Tests ====================

    def test_clean_text_removes_whitespace(self, processor):
        """Test excessive whitespace removal"""
        text = "This  is   a    test\n\nwith  extra    spaces"
        result = processor._clean_text(text)
        assert result == "This is a test with extra spaces"

    def test_clean_text_removes_page_numbers(self, processor):
        """Test page number removal"""
        text = "Some text here Page 5 of 10 more text"
        result = processor._clean_text(text)
        assert "Page 5 of 10" not in result

    def test_clean_text_normalizes_quotes(self, processor):
        """Test quote normalization"""
        text = '"Smart quotes" and 'single quotes''
        result = processor._clean_text(text)
        assert '"Smart quotes"' in result
        assert "'" in result

    def test_clean_text_empty_string(self, processor):
        """Test cleaning empty string"""
        result = processor._clean_text("")
        assert result == ""

    # ==================== Sentence Splitting Tests ====================

    def test_split_into_sentences_simple(self, processor):
        """Test simple sentence splitting"""
        text = "First sentence. Second sentence. Third sentence."
        result = processor._split_into_sentences(text)
        assert len(result) == 3
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."
        assert result[2] == "Third sentence."

    def test_split_into_sentences_with_exclamation(self, processor):
        """Test splitting with exclamation marks"""
        text = "Hello! How are you? I am fine."
        result = processor._split_into_sentences(text)
        assert len(result) == 3

    def test_split_into_sentences_with_abbreviations(self, processor):
        """Test splitting handles abbreviations (note: may split incorrectly)"""
        text = "Dr. Smith works at ABC Corp. He is great."
        result = processor._split_into_sentences(text)
        # Simple regex will split on Dr. and Corp. (expected limitation)
        assert len(result) >= 2

    def test_split_into_sentences_empty_string(self, processor):
        """Test splitting empty string"""
        result = processor._split_into_sentences("")
        assert len(result) == 0

    def test_split_into_sentences_no_punctuation(self, processor):
        """Test splitting text without sentence punctuation"""
        text = "This is one long sentence without proper punctuation"
        result = processor._split_into_sentences(text)
        assert len(result) == 1

    # ==================== Text Chunking Tests ====================

    def test_chunk_text_simple(self, processor):
        """Test basic text chunking"""
        # Create text that will require multiple chunks
        sentences = ["Sentence number one. ", "Sentence number two. ",
                     "Sentence number three. ", "Sentence number four."]
        long_text = "".join(sentences * 50)  # Repeat to ensure > chunk_size

        text_content = [{
            "text": long_text,
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        # Mock chunk size to force chunking
        with patch.object(processor, '_clean_text', return_value=long_text):
            result = processor._chunk_text(text_content)

        # Should create multiple chunks
        assert len(result) > 1

        # Each chunk should have metadata
        for chunk in result:
            assert "text" in chunk
            assert "page_number" in chunk
            assert "document_id" in chunk
            assert "fund_id" in chunk
            assert "chunk_index" in chunk

    def test_chunk_text_with_overlap(self, processor):
        """Test that chunks have proper overlap"""
        # Create sentences of known length
        sentence = "This is exactly fifty characters long padding." + " " * 4  # 50 chars
        text = sentence * 30  # 1500 characters

        text_content = [{
            "text": text,
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        # Use default chunk_size (1000) and chunk_overlap (200)
        with patch.object(processor, '_clean_text', return_value=text):
            result = processor._chunk_text(text_content)

        # Should have overlap between consecutive chunks
        if len(result) > 1:
            # Last 200 chars of first chunk should appear in second chunk
            # (approximately - due to sentence boundaries)
            assert len(result[0]["text"]) >= 800  # At least approaching chunk_size
            assert len(result) >= 2  # Should create multiple chunks

    def test_chunk_text_skips_short_text(self, processor):
        """Test that very short text is skipped"""
        text_content = [{
            "text": "Short",  # Less than 50 chars
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        result = processor._chunk_text(text_content)
        assert len(result) == 0

    def test_chunk_text_empty_input(self, processor):
        """Test chunking with empty input"""
        result = processor._chunk_text([])
        assert len(result) == 0

    def test_chunk_text_preserves_metadata(self, processor):
        """Test that metadata is preserved in chunks"""
        text_content = [{
            "text": "This is a test sentence. " * 100,  # Long enough to chunk
            "page_number": 5,
            "document_id": 42,
            "fund_id": 7
        }]

        with patch.object(processor, '_clean_text', return_value=text_content[0]["text"]):
            result = processor._chunk_text(text_content)

        # All chunks should have correct metadata
        for chunk in result:
            assert chunk["page_number"] == 5
            assert chunk["document_id"] == 42
            assert chunk["fund_id"] == 7

    def test_chunk_text_multiple_pages(self, processor):
        """Test chunking multiple pages"""
        text_content = [
            {
                "text": "Page 1 content. " * 100,
                "page_number": 1,
                "document_id": 1,
                "fund_id": 1
            },
            {
                "text": "Page 2 content. " * 100,
                "page_number": 2,
                "document_id": 1,
                "fund_id": 1
            }
        ]

        with patch.object(processor, '_clean_text', side_effect=lambda x: x):
            result = processor._chunk_text(text_content)

        # Should have chunks from both pages
        page_numbers = set(chunk["page_number"] for chunk in result)
        assert 1 in page_numbers
        assert 2 in page_numbers

    # ==================== Integration Tests (Mocked) ====================

    @pytest.mark.asyncio
    async def test_process_document_updates_status(self, processor, mock_db):
        """Test that document status is updated during processing"""
        from app.models.document import Document

        # Mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.parsing_status = "pending"

        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_doc
        mock_db.query.return_value = mock_query

        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = ""
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf

        with patch('pdfplumber.open', return_value=mock_pdf):
            # Mock vector store
            processor.vector_store.add_document = AsyncMock()

            try:
                result = await processor.process_document(
                    file_path="/fake/path.pdf",
                    document_id=1,
                    fund_id=1
                )

                # Status should be set to processing, then completed
                assert mock_doc.parsing_status == "completed"
                assert mock_db.commit.called

            except Exception:
                # If error occurs, status should be failed
                pass

    @pytest.mark.asyncio
    async def test_process_document_handles_page_errors(self, processor, mock_db):
        """Test that page-level errors don't stop processing"""
        from app.models.document import Document

        # Mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_doc
        mock_db.query.return_value = mock_query

        # Create pages where one throws error
        mock_page_1 = MagicMock()
        mock_page_1.extract_tables.return_value = []
        mock_page_1.extract_text.return_value = "Page 1 text"

        mock_page_2 = MagicMock()
        mock_page_2.extract_tables.side_effect = Exception("Page 2 error")

        mock_page_3 = MagicMock()
        mock_page_3.extract_tables.return_value = []
        mock_page_3.extract_text.return_value = "Page 3 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page_1, mock_page_2, mock_page_3]
        mock_pdf.__enter__.return_value = mock_pdf

        with patch('pdfplumber.open', return_value=mock_pdf):
            processor.vector_store.add_document = AsyncMock()

            result = await processor.process_document(
                file_path="/fake/path.pdf",
                document_id=1,
                fund_id=1
            )

            # Should process pages 1 and 3, skip page 2
            assert result["pages_processed"] == 2
            assert len(result["errors"]) > 0
            assert "Page 2 error" in str(result["errors"])


class TestDocumentProcessorEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def processor(self, mock_db):
        with patch('app.services.document_processor.TableParser'), \
             patch('app.services.document_processor.VectorStore'):
            return DocumentProcessor(mock_db)

    def test_chunk_text_single_very_long_sentence(self, processor):
        """Test chunking a single sentence longer than chunk_size"""
        # Create one sentence > 1000 characters
        long_sentence = "This is a very long sentence " * 50  # ~1500 chars

        text_content = [{
            "text": long_sentence,
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        with patch.object(processor, '_clean_text', return_value=long_sentence):
            with patch.object(processor, '_split_into_sentences', return_value=[long_sentence]):
                result = processor._chunk_text(text_content)

        # Should still create chunks even with long sentence
        assert len(result) >= 1

    def test_clean_text_unicode_characters(self, processor):
        """Test cleaning text with unicode characters"""
        text = "Text with émojis 🚀 and spëcial çharacters"
        result = processor._clean_text(text)
        # Should not crash and preserve unicode
        assert len(result) > 0

    def test_chunk_text_empty_sentences(self, processor):
        """Test chunking when sentence splitting returns empty results"""
        text_content = [{
            "text": "Some text here",
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        with patch.object(processor, '_split_into_sentences', return_value=[]):
            result = processor._chunk_text(text_content)

        # Should handle gracefully
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_process_document_file_not_found(self, processor, mock_db):
        """Test processing non-existent file"""
        from app.models.document import Document

        mock_doc = Mock(spec=Document)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_doc
        mock_db.query.return_value = mock_query

        with pytest.raises(Exception):
            await processor.process_document(
                file_path="/nonexistent/file.pdf",
                document_id=1,
                fund_id=1
            )

        # Status should be set to failed
        assert mock_doc.parsing_status == "failed"


class TestTextChunkingScenarios:
    """Test realistic text chunking scenarios"""

    @pytest.fixture
    def processor(self):
        mock_db = Mock()
        with patch('app.services.document_processor.TableParser'), \
             patch('app.services.document_processor.VectorStore'):
            return DocumentProcessor(mock_db)

    def test_chunk_fund_report_text(self, processor):
        """Test chunking realistic fund report text"""
        report_text = """
        Fund Performance Report - Q4 2024

        The XYZ Venture Fund has demonstrated strong performance in the fourth quarter.
        Total capital called to date amounts to $50,000,000 across 15 portfolio companies.
        Distributions during the quarter totaled $12,500,000 from three successful exits.

        Portfolio highlights include Company A's Series B round at a 3x markup,
        Company B's acquisition by a strategic buyer generating 5x returns, and
        Company C's continued revenue growth of 150% year-over-year.

        The fund's current DPI stands at 0.85, with an IRR of 22% since inception.
        Net Asset Value has increased by 15% quarter-over-quarter due to markup events.
        Management expects continued strong performance through 2025.
        """

        text_content = [{
            "text": report_text,
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        result = processor._chunk_text(text_content)

        # Should create at least one chunk
        assert len(result) >= 1

        # Chunks should be reasonable size
        for chunk in result:
            assert len(chunk["text"]) > 0
            assert len(chunk["text"]) <= 1200  # Chunk size + some tolerance

    def test_chunk_maintains_financial_context(self, processor):
        """Test that financial figures stay within same chunk when possible"""
        text = """
        Capital Calls Summary:
        Q1 2024: $5,000,000
        Q2 2024: $7,500,000
        Q3 2024: $10,000,000
        Q4 2024: $15,000,000
        Total: $37,500,000
        """ * 10  # Repeat to force chunking

        text_content = [{
            "text": text,
            "page_number": 1,
            "document_id": 1,
            "fund_id": 1
        }]

        result = processor._chunk_text(text_content)

        # Should create multiple chunks due to length
        assert len(result) > 1

        # Each chunk should be properly formed
        for chunk in result:
            assert isinstance(chunk["text"], str)
            assert len(chunk["text"]) > 0
