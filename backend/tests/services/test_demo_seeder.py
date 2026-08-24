import pytest
from unittest.mock import patch, MagicMock
from services.demo_seeder import seed_demo_data
from services.demo_constants import DEMO_FAMILY_PROFILE, DEMO_PORTFOLIO_DATA, DEMO_ALT_INVESTMENT
import config

@pytest.fixture
def mock_db_manager():
    with patch("services.demo_seeder.db_manager") as m:
        yield m

def test_seed_demo_data_success(mock_db_manager):
    """Test successful seeding of both HE and EN demo data."""
    # Arrange
    mock_doc = MagicMock()
    mock_db_manager.db.collection.return_value.document.return_value.collection.return_value.list_documents.return_value = [mock_doc]

    # Act
    seed_demo_data()

    # Assert
    # 1. Family Profile assertions (called for demo-user-12345 and demo-user-en)
    assert mock_db_manager.save_family_profile.call_count == 2
    uids_saved = [c[0][0] for c in mock_db_manager.save_family_profile.call_args_list]
    assert config.DEMO_UID in uids_saved
    assert "demo-user-en" in uids_saved

    # 2. Portfolio assertions
    assert mock_db_manager.save_processed_portfolio.call_count == 2

    # 3. Alternative Investments assertions
    assert mock_db_manager.add_alt_project.call_count == 2

    # 4. Insurance RAG chunks assertions
    assert mock_db_manager.save_policy_chunks.call_count == 2

def test_seed_demo_data_exception_on_delete(mock_db_manager):
    """Test that seeding continues successfully even if deleting existing alt_projects throws an exception."""
    # Arrange
    mock_db_manager.db.collection.return_value.document.return_value.collection.return_value.list_documents.side_effect = Exception("Firestore Error")

    # Act
    seed_demo_data()

    # Assert
    assert mock_db_manager.add_alt_project.call_count == 2
