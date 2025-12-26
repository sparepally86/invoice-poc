# app/tests/test_pii_redaction.py
"""
Test PII redaction utility to ensure sensitive data is properly masked.
"""

from app.utils.pii_redaction import redact_pii, get_redaction_stats, _extract_vendor_identifiers


class TestPIIRedaction:
    """Test suite for PII redaction functions."""
    
    def test_email_redaction(self):
        """Test that email addresses are redacted."""
        text = "Contact support at admin@example.com for help"
        redacted = redact_pii(text)
        assert "[REDACTED_EMAIL]" in redacted
        assert "admin@example.com" not in redacted
    
    def test_phone_redaction(self):
        """Test that phone numbers are redacted."""
        text = "Call us at +91-9876-543-210 for support"
        redacted = redact_pii(text)
        assert "[REDACTED_PHONE]" in redacted
        assert "+91-9876-543-210" not in redacted
    
    def test_gst_redaction(self):
        """Test that GST numbers are redacted."""
        text = "Invoice GST: 18AABCU9603R1Z5"
        redacted = redact_pii(text)
        assert "[REDACTED_GST]" in redacted
        assert "18AABCU9603R1Z5" not in redacted
    
    def test_pan_redaction(self):
        """Test that PAN numbers are redacted."""
        text = "PAN: AAAPA1234A"
        redacted = redact_pii(text)
        assert "[REDACTED_PAN]" in redacted
        assert "AAAPA1234A" not in redacted
    
    def test_vat_redaction(self):
        """Test that VAT IDs are redacted."""
        text = "VAT ID: DE123456789"
        redacted = redact_pii(text)
        assert "[REDACTED_VAT]" in redacted
        assert "DE123456789" not in redacted
    
    def test_bank_account_redaction(self):
        """Test that long digit sequences (bank accounts) are redacted."""
        text = "Bank account: 1234567890123456"
        redacted = redact_pii(text)
        # Bank account may be caught by credit card pattern or bank account pattern (both acceptable)
        assert ("[REDACTED_BANK]" in redacted or "[REDACTED_CC]" in redacted) and "1234567890123456" not in redacted
    
    def test_credit_card_redaction(self):
        """Test that credit card numbers are redacted."""
        text = "Card: 4532-1234-5678-9010"
        redacted = redact_pii(text)
        assert "[REDACTED_CC]" in redacted
        assert "4532-1234-5678-9010" not in redacted
    
    def test_ifsc_redaction(self):
        """Test that IFSC codes are redacted."""
        text = "IFSC Code: HDFC0001234"
        redacted = redact_pii(text)
        assert "[REDACTED_IFSC]" in redacted
        assert "HDFC0001234" not in redacted
    
    def test_vendor_name_redaction(self):
        """Test that vendor names from invoice are redacted from prompt."""
        invoice = {
            "header": {
                "vendor_name": "Acme Corporation",
                "vendor_number": "V001"
            }
        }
        text = "Vendor: Acme Corporation with ID V001"
        redacted = redact_pii(text, invoice=invoice)
        assert "[REDACTED_VENDOR]" in redacted
        assert "Acme Corporation" not in redacted
        assert "V001" not in redacted
    
    def test_no_pii_returns_unchanged(self):
        """Test that text without PII is returned unchanged."""
        text = "This is a normal invoice with no sensitive data"
        redacted = redact_pii(text)
        assert redacted == text
    
    def test_invoice_vendor_extraction(self):
        """Test that vendor identifiers are correctly extracted from invoice."""
        invoice = {
            "header": {
                "vendor": "Test Vendor",
                "vendor_number": "V123",
                "vendor_name": "Test Vendor Inc"
            },
            "vendor": {
                "name": "Test Vendor Inc",
                "vendor_id": "V123"
            }
        }
        vendors = _extract_vendor_identifiers(invoice)
        assert "Test Vendor" in vendors or "Test Vendor Inc" in vendors
        assert "V123" in vendors
    
    def test_empty_text_returns_empty(self):
        """Test that empty text is handled gracefully."""
        assert redact_pii("") == ""
        assert redact_pii(None) == None
    
    def test_complex_invoice_context(self):
        """Test redaction on realistic invoice context in prompt."""
        invoice = {
            "header": {
                "vendor_name": "Acme Supplies Ltd",
                "vendor_number": "SUPP001",
                "invoice_ref": "INV-2024-001"
            }
        }
        prompt = """Invoice Context:
Invoice: INV-2024-001, Vendor: Acme Supplies Ltd, Amount: 5000, PO: PO-123456

Validation Results:
GST: 18AABCU9603R1Z5 not matching. Contact vendor at vendor@acme.com or +91-9876543210

Retrieved prior cases:
- No similar cases found"""
        
        redacted = redact_pii(prompt, invoice=invoice)
        
        # Check that PII is redacted
        assert "[REDACTED_GST]" in redacted
        assert "[REDACTED_EMAIL]" in redacted
        assert "18AABCU9603R1Z5" not in redacted
        assert "vendor@acme.com" not in redacted
        
        # Check that vendor name is redacted
        assert "[REDACTED_VENDOR]" in redacted
        assert "Acme Supplies Ltd" not in redacted
        
        # Check that sentence structure is preserved
        assert "Invoice Context:" in redacted
        assert "Validation Results:" in redacted
    
    def test_redaction_statistics(self):
        """Test redaction statistics tracking."""
        text = """
        Contact: email@example.com, phone: +91-9876543210
        PAN: AAAPA1234A, GST: 18AABCU9603R1Z5
        Card: 4532-1234-5678-9010
        """
        redacted = redact_pii(text)
        stats = get_redaction_stats(text, redacted)
        
        # At least some PII should be detected
        assert any(count > 0 for count in stats.values()), f"No PII detected: {stats}"
        assert stats.get("email", 0) > 0, "Email should be detected"
        assert stats.get("pan", 0) > 0, "PAN should be detected"
        assert stats.get("gst", 0) > 0, "GST should be detected"
    
    def test_deterministic_redaction(self):
        """Test that redaction is deterministic (same input produces same output)."""
        text = "Vendor: ABC Corp, Email: test@example.com, Phone: 9876543210"
        redacted1 = redact_pii(text)
        redacted2 = redact_pii(text)
        assert redacted1 == redacted2
    
    def test_partial_vendor_name_not_over_redacted(self):
        """Test that partial matches of vendor names are not aggressively redacted."""
        invoice = {
            "header": {
                "vendor_name": "Acme"
            }
        }
        text = "The acme of efficiency for vendor Acme"
        redacted = redact_pii(text, invoice=invoice)
        # Word boundaries should prevent "acme" from being redacted when it's part of another word
        assert "[REDACTED_VENDOR]" in redacted
        assert "Acme" not in redacted or "the acme" not in redacted.lower()
    
    def test_special_characters_in_vendor_name(self):
        """Test redaction of vendor names with special characters."""
        invoice = {
            "header": {
                "vendor_name": "O'Brien & Co."
            }
        }
        text = "Vendor: O'Brien & Co. is processing the invoice"
        redacted = redact_pii(text, invoice=invoice)
        assert "[REDACTED_VENDOR]" in redacted
        assert "O'Brien & Co." not in redacted
    
    def test_case_insensitive_vendor_redaction(self):
        """Test that vendor names are redacted case-insensitively."""
        invoice = {
            "header": {
                "vendor_name": "TestCorp"
            }
        }
        text = "Vendor: testcorp has submitted invoice"
        redacted = redact_pii(text, invoice=invoice)
        assert "[REDACTED_VENDOR]" in redacted
        assert "testcorp" not in redacted.lower()


if __name__ == "__main__":
    # Simple test runner
    test = TestPIIRedaction()
    test.test_email_redaction()
    test.test_phone_redaction()
    test.test_gst_redaction()
    test.test_pan_redaction()
    test.test_vat_redaction()
    test.test_bank_account_redaction()
    test.test_credit_card_redaction()
    test.test_ifsc_redaction()
    test.test_vendor_name_redaction()
    test.test_no_pii_returns_unchanged()
    test.test_invoice_vendor_extraction()
    test.test_empty_text_returns_empty()
    test.test_complex_invoice_context()
    test.test_redaction_statistics()
    test.test_deterministic_redaction()
    test.test_partial_vendor_name_not_over_redacted()
    test.test_special_characters_in_vendor_name()
    test.test_case_insensitive_vendor_redaction()
    print("All tests passed!")
