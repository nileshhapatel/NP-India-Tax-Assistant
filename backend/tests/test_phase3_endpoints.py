"""
Tests for Phase 3 REST API Endpoints

Tests all Phase 3 specialist endpoints:
- POST /api/phase3/optimize/tax-savings
- POST /api/phase3/validate/compliance
- POST /api/phase3/reconcile/three-way
- POST /api/phase3/track/lifecycle-event
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


# ============================================================================
# TAX SAVINGS OPTIMIZER ENDPOINT TESTS
# ============================================================================


class TestTaxSavingsOptimizeEndpoint:
    """Test /api/phase3/optimize/tax-savings endpoint"""
    
    def test_basic_optimization_request(self):
        """Test basic tax optimization request"""
        payload = {
            "total_income": 800000,
            "current_deductions": 100000,
            "tax_paid": 150000,
            "residency_status": "ROR",
            "current_regime": "old",
            "age": 40,
            "has_home_loan": False,
            "has_dependents": False,
            "investment_capacity": 100000,
            "risk_profile": "moderate"
        }
        
        response = client.post("/api/phase3/optimize/tax-savings", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "analysis" in data
        assert "strategies" in data["analysis"]
        assert len(data["analysis"]["strategies"]) > 0
        assert "total_potential_saving" in data["analysis"]
        assert "priority_actions" in data["analysis"]
    
    def test_nri_optimization_request(self):
        """Test NRI-specific optimization"""
        payload = {
            "total_income": 500000,
            "current_deductions": 0,
            "tax_paid": 100000,
            "residency_status": "NRI",
            "current_regime": "new",
            "age": 35,
            "has_home_loan": False,
            "investment_capacity": 150000,
            "risk_profile": "moderate"
        }
        
        response = client.post("/api/phase3/optimize/tax-savings", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "analysis" in data
    
    def test_with_dependents(self):
        """Test optimization with dependents"""
        payload = {
            "total_income": 1000000,
            "current_deductions": 150000,
            "tax_paid": 200000,
            "residency_status": "ROR",
            "current_regime": "old",
            "age": 40,
            "has_home_loan": True,
            "has_dependents": True,
            "num_dependents": 2,
            "investment_capacity": 200000,
            "risk_profile": "conservative"
        }
        
        response = client.post("/api/phase3/optimize/tax-savings", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


# ============================================================================
# COMPLIANCE VALIDATOR ENDPOINT TESTS
# ============================================================================


class TestComplianceValidatorEndpoint:
    """Test /api/phase3/validate/compliance endpoint"""
    
    def test_compliant_filing(self):
        """Test compliant tax return"""
        payload = {
            "total_income": 600000,
            "residency_status": "ROR",
            "deductions": {
                "80c": 100000,
                "80d": 50000
            },
            "tds_claimed": 75000,
            "ais_received": True,
            "form_26as_received": True,
            "assessment_year": 2027
        }
        
        response = client.post("/api/phase3/validate/compliance", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "compliance" in data
        assert "compliance_score" in data["compliance"]
        assert "violations" in data["compliance"]
        assert isinstance(data["compliance"]["compliance_score"], (int, float))
    
    def test_non_resident_deduction_violation(self):
        """Test NRI attempting invalid deductions"""
        payload = {
            "total_income": 500000,
            "residency_status": "NRI",
            "deductions": {
                "80c": 100000,  # NRIs cannot claim 80C
                "80d": 0
            },
            "tds_claimed": 0,
            "ais_received": True,
            "form_26as_received": True,
            "assessment_year": 2027
        }
        
        response = client.post("/api/phase3/validate/compliance", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        # Should have violations
        assert len(data["compliance"]["violations"]) > 0
    
    def test_tds_mismatch_detection(self):
        """Test TDS mismatch detection"""
        payload = {
            "total_income": 400000,
            "residency_status": "ROR",
            "deductions": {},
            "tds_claimed": 150000,  # More TDS than income
            "ais_received": True,
            "form_26as_received": True,
            "assessment_year": 2027
        }
        
        response = client.post("/api/phase3/validate/compliance", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


# ============================================================================
# RECONCILIATION EXPERT ENDPOINT TESTS
# ============================================================================


class TestReconciliationExpertEndpoint:
    """Test /api/phase3/reconcile/three-way endpoint"""
    
    def test_three_way_reconciliation(self):
        """Test three-way reconciliation"""
        payload = {
            "source_statements": [
                {
                    "id": "s1",
                    "date": "2026-04-15",
                    "amount": 50000,
                    "description": "Interest received",
                    "source_type": "bank_statement",
                    "document_ref": "Page 1"
                }
            ],
            "ais_entries": [
                {
                    "id": "a1",
                    "date": "2026-04-15",
                    "amount": 50000,
                    "category": "interest",
                    "payer_name": "Bank",
                    "payer_pan": "AAAB12345D",
                    "deductee_code": "BNI",
                    "form_26as_section": "194A"
                }
            ],
            "itr_entries": [
                {
                    "id": "i1",
                    "date": "2026-04-15",
                    "amount": 50000,
                    "category": "interest_income",
                    "description": "Bank interest",
                    "form_line_item": "Schedule OS"
                }
            ]
        }
        
        response = client.post("/api/phase3/reconcile/three-way", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "reconciliation" in data
        assert "total_matched" in data["reconciliation"]
        assert "risk_rating" in data["reconciliation"]
        assert "filing_readiness" in data["reconciliation"]
    
    def test_unmatched_entries_detection(self):
        """Test detection of unmatched entries"""
        payload = {
            "source_statements": [
                {
                    "id": "s1",
                    "date": "2026-04-15",
                    "amount": 50000,
                    "description": "Interest",
                    "source_type": "bank_statement",
                    "document_ref": "Page 1"
                }
            ],
            "ais_entries": [],  # No AIS entries
            "itr_entries": []   # No ITR entries
        }
        
        response = client.post("/api/phase3/reconcile/three-way", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["reconciliation"]["total_unmatched_source"] == 1


# ============================================================================
# LIFECYCLE TRACKER ENDPOINT TESTS
# ============================================================================


class TestLifecycleTrackerEndpoint:
    """Test /api/phase3/track/lifecycle-event endpoint"""
    
    def test_birth_event_tracking(self):
        """Test tracking birth event"""
        payload = {
            "event_type": "birth",
            "category": "family",
            "date_occurred": "2026-03-15",
            "description": "Birth of child",
            "affected_person": "child"
        }
        
        response = client.post("/api/phase3/track/lifecycle-event", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "lifecycle_impact" in data
        assert "deduction_changes" in data["lifecycle_impact"]
        assert "actions_needed" in data["lifecycle_impact"]
    
    def test_home_purchase_event(self):
        """Test home purchase event"""
        payload = {
            "event_type": "home_purchase",
            "category": "property",
            "date_occurred": "2026-05-20",
            "description": "Home purchase",
            "affected_person": "self",
            "metadata": {
                "loan_amount": "2000000"
            }
        }
        
        response = client.post("/api/phase3/track/lifecycle-event", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["lifecycle_impact"]["high_priority"] is True
    
    def test_residency_change_event(self):
        """Test residency change event"""
        payload = {
            "event_type": "left_india",
            "category": "residency",
            "date_occurred": "2026-06-01",
            "description": "Moved abroad",
            "affected_person": "self",
            "metadata": {
                "destination_country": "US"
            }
        }
        
        response = client.post("/api/phase3/track/lifecycle-event", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "residency_impact" in data["lifecycle_impact"]


# ============================================================================
# BATCH OPERATIONS TESTS
# ============================================================================


class TestBatchOperations:
    """Test batch endpoints for multiple taxpayers"""
    
    def test_batch_optimization(self):
        """Test batch optimization for family"""
        payload = {
            "taxpayers": [
                {
                    "total_income": 800000,
                    "current_deductions": 100000,
                    "tax_paid": 150000,
                    "residency_status": "ROR",
                    "current_regime": "old",
                    "age": 40,
                    "has_home_loan": True,
                    "investment_capacity": 100000,
                    "risk_profile": "moderate"
                },
                {
                    "total_income": 600000,
                    "current_deductions": 50000,
                    "tax_paid": 100000,
                    "residency_status": "ROR",
                    "current_regime": "new",
                    "age": 38,
                    "has_home_loan": False,
                    "investment_capacity": 150000,
                    "risk_profile": "conservative"
                }
            ]
        }
        
        response = client.post("/api/phase3/optimize/batch", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["total"] == 2
        assert data["successful"] == 2


# ============================================================================
# ENDPOINT HEALTH TESTS
# ============================================================================


class TestEndpointHealth:
    """Test endpoint availability and error handling"""
    
    def test_health_check_endpoint(self):
        """Verify health endpoint works"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_invalid_residency_status(self):
        """Test error handling for invalid residency"""
        payload = {
            "total_income": 800000,
            "current_deductions": 100000,
            "tax_paid": 150000,
            "residency_status": "INVALID",  # Invalid status
            "current_regime": "old",
            "age": 40,
            "has_home_loan": False,
            "investment_capacity": 100000,
            "risk_profile": "moderate"
        }
        
        response = client.post("/api/phase3/optimize/tax-savings", json=payload)
        
        # Should return error (400 or similar)
        assert response.status_code >= 400
    
    def test_missing_required_fields(self):
        """Test error handling for missing required fields"""
        payload = {
            "total_income": 800000,
            # Missing other required fields
        }
        
        response = client.post("/api/phase3/optimize/tax-savings", json=payload)
        
        # Should return validation error
        assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
