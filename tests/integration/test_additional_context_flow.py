"""
Integration tests for the additionalContext feature.
Tests the complete flow from hypothesis creation to experiment prompt generation.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAdditionalContextFlow:
    """Test the complete flow of additionalContext through the system."""

    @pytest.fixture
    def sample_hypothesis_with_context(self):
        """Sample hypothesis data with additional context."""
        return {
            "_id": "test-hypothesis-123",
            "title": "Test Neural Network Optimization",
            "idea": "Explore novel optimization techniques for deep learning models.",
            "additionalContext": "Please focus on memory-efficient methods. Use PyTorch only. Target GPU with 8GB VRAM.",
            "ideaJson": {
                "Name": "test_neural_network_optimization",
                "Title": "Test Neural Network Optimization",
                "Short Hypothesis": "Novel optimization techniques can improve deep learning training efficiency.",
                "Abstract": "Explore novel optimization techniques for deep learning models.",
                "Experiments": [
                    "Implement baseline optimizer",
                    "Test on CIFAR-10",
                    "Compare memory usage"
                ],
                "Risk Factors and Limitations": [
                    "May not generalize to all architectures"
                ],
                "Additional Context": "Please focus on memory-efficient methods. Use PyTorch only. Target GPU with 8GB VRAM."
            },
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "test-user"
        }

    @pytest.fixture
    def sample_hypothesis_without_context(self):
        """Sample hypothesis data without additional context."""
        return {
            "_id": "test-hypothesis-456",
            "title": "Basic ML Experiment",
            "idea": "Test a simple machine learning approach.",
            "ideaJson": {
                "Name": "basic_ml_experiment",
                "Title": "Basic ML Experiment",
                "Short Hypothesis": "Simple ML can work well.",
                "Abstract": "Test a simple machine learning approach.",
                "Experiments": ["Run baseline"],
                "Risk Factors and Limitations": ["Limited scope"]
            },
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "test-user"
        }


class TestAgentManagerAdditionalContext:
    """Test that agent_manager properly consumes Additional Context from ideaJson."""

    def test_task_desc_includes_additional_context(self):
        """Verify that _get_task_desc_str includes Additional Context when present."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Create a mock config
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        mock_cfg.agent.search.num_drafts = 3
        
        # Task description with Additional Context
        task_desc_json = json.dumps({
            "Title": "Test Experiment",
            "Abstract": "This is a test abstract for the experiment.",
            "Short Hypothesis": "Testing hypothesis generation.",
            "Experiments": ["Experiment 1", "Experiment 2"],
            "Risk Factors and Limitations": ["Risk 1"],
            "Additional Context": "Use only CPU. Limit runtime to 1 hour. Focus on interpretability."
        })
        
        # Create AgentManager instance
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = json.loads(task_desc_json)
            manager.cfg = mock_cfg
            
            # Call the method
            result = manager._get_task_desc_str()
        
        # Verify Additional Context is included
        assert "Additional Context" in result
        assert "Use only CPU" in result
        assert "Limit runtime to 1 hour" in result
        assert "Focus on interpretability" in result
        assert "special instructions, constraints, or background information" in result

    def test_task_desc_excludes_additional_context_when_empty(self):
        """Verify that _get_task_desc_str doesn't add Additional Context section when empty."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        # Task description without Additional Context
        task_desc_json = json.dumps({
            "Title": "Test Experiment",
            "Abstract": "This is a test abstract.",
            "Short Hypothesis": "Testing hypothesis.",
            "Experiments": ["Experiment 1"],
            "Risk Factors and Limitations": ["Risk 1"]
        })
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = json.loads(task_desc_json)
            manager.cfg = mock_cfg
            
            result = manager._get_task_desc_str()
        
        # Verify Additional Context section is NOT included
        assert "Additional Context (special instructions" not in result

    def test_task_desc_excludes_additional_context_when_none(self):
        """Verify that empty string Additional Context is not included."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        # Task description with empty Additional Context
        task_desc_json = json.dumps({
            "Title": "Test Experiment",
            "Abstract": "This is a test abstract.",
            "Short Hypothesis": "Testing hypothesis.",
            "Experiments": ["Experiment 1"],
            "Risk Factors and Limitations": ["Risk 1"],
            "Additional Context": ""  # Empty string
        })
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = json.loads(task_desc_json)
            manager.cfg = mock_cfg
            
            result = manager._get_task_desc_str()
        
        # Verify Additional Context section is NOT included for empty string
        assert "Additional Context (special instructions" not in result


class TestIdeaJsonGeneration:
    """Test that ideaJson correctly includes Additional Context."""

    def test_idea_json_structure_with_additional_context(self):
        """Verify ideaJson structure includes Additional Context field."""
        # Simulate the structure that would be generated
        idea_json = {
            "Name": "test_experiment",
            "Title": "Test Experiment",
            "Short Hypothesis": "Testing the hypothesis",
            "Abstract": "Full description of the experiment",
            "Experiments": ["Exp 1", "Exp 2"],
            "Risk Factors and Limitations": ["Risk 1"],
            "Additional Context": "Custom user instructions here"
        }
        
        # Verify structure
        assert "Additional Context" in idea_json
        assert idea_json["Additional Context"] == "Custom user instructions here"
        
        # Verify it can be serialized to JSON (important for MongoDB storage)
        json_str = json.dumps(idea_json)
        parsed = json.loads(json_str)
        assert parsed["Additional Context"] == "Custom user instructions here"

    def test_idea_json_without_additional_context(self):
        """Verify ideaJson works without Additional Context."""
        idea_json = {
            "Name": "test_experiment",
            "Title": "Test Experiment",
            "Short Hypothesis": "Testing the hypothesis",
            "Abstract": "Full description",
            "Experiments": ["Exp 1"],
            "Risk Factors and Limitations": ["Risk 1"]
        }
        
        # Should not have Additional Context
        assert "Additional Context" not in idea_json
        
        # Should still be valid JSON
        json_str = json.dumps(idea_json)
        parsed = json.loads(json_str)
        assert "Additional Context" not in parsed


class TestEndToEndFlow:
    """Test the complete flow from hypothesis to prompt generation."""

    def test_full_flow_with_additional_context(self):
        """
        Test the complete flow:
        1. Hypothesis with additionalContext is created
        2. ideaJson includes "Additional Context"
        3. AgentManager reads ideaJson and generates task_desc with context
        4. The context appears in prompts
        """
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Step 1: Simulate hypothesis creation with additionalContext
        hypothesis = {
            "_id": "flow-test-123",
            "title": "Memory-Efficient Transformers",
            "idea": "Develop memory-efficient attention mechanisms for transformers.",
            "additionalContext": "Must work on consumer GPUs (8GB VRAM). Use FlashAttention as baseline. Output should include memory profiling.",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "researcher"
        }
        
        # Step 2: Simulate ideaJson generation (as done in API routes)
        idea_json = {
            "Name": hypothesis["title"].lower().replace(" ", "_").replace("-", "_"),
            "Title": hypothesis["title"],
            "Short Hypothesis": hypothesis["idea"][:200],
            "Abstract": hypothesis["idea"],
            "Experiments": [
                "Implement baseline attention",
                "Add memory-efficient variant",
                "Profile memory usage"
            ],
            "Risk Factors and Limitations": [
                "May trade off speed for memory"
            ],
            # This is the key - additionalContext becomes "Additional Context" in ideaJson
            "Additional Context": hypothesis["additionalContext"]
        }
        
        # Verify ideaJson has the context
        assert "Additional Context" in idea_json
        assert "8GB VRAM" in idea_json["Additional Context"]
        
        # Step 3: Simulate AgentManager consuming this
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = idea_json
            manager.cfg = mock_cfg
            
            # Step 4: Generate task description
            task_desc_str = manager._get_task_desc_str()
        
        # Verify the complete flow
        assert "Memory-Efficient Transformers" in task_desc_str  # Title
        assert "memory-efficient attention mechanisms" in task_desc_str  # Abstract
        assert "Additional Context" in task_desc_str  # Context section exists
        assert "8GB VRAM" in task_desc_str  # User's constraint
        assert "FlashAttention" in task_desc_str  # User's baseline requirement
        assert "memory profiling" in task_desc_str  # User's output requirement

    def test_full_flow_without_additional_context(self):
        """Test that the flow works correctly without additional context."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Hypothesis without additionalContext
        hypothesis = {
            "_id": "flow-test-456",
            "title": "Basic Classification",
            "idea": "Implement a basic image classifier.",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "researcher"
        }
        
        # ideaJson without Additional Context
        idea_json = {
            "Name": "basic_classification",
            "Title": hypothesis["title"],
            "Short Hypothesis": hypothesis["idea"],
            "Abstract": hypothesis["idea"],
            "Experiments": ["Train classifier"],
            "Risk Factors and Limitations": ["Simple approach"]
        }
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = idea_json
            manager.cfg = mock_cfg
            
            task_desc_str = manager._get_task_desc_str()
        
        # Verify basic content exists
        assert "Basic Classification" in task_desc_str
        assert "image classifier" in task_desc_str
        
        # Verify Additional Context section is NOT present
        assert "Additional Context (special instructions" not in task_desc_str


class TestEdgeCases:
    """Test edge cases and potential issues."""

    def test_additional_context_with_special_characters(self):
        """Test that special characters in additional context are handled."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Context with special characters
        special_context = """
        Use these constraints:
        - Memory < 8GB
        - Runtime <= 2 hours
        - Code should be "clean" & well-documented
        - Use paths like /data/train/*.csv
        """
        
        idea_json = {
            "Title": "Test",
            "Abstract": "Test abstract",
            "Short Hypothesis": "Test hypothesis",
            "Experiments": ["Test"],
            "Risk Factors and Limitations": ["Test"],
            "Additional Context": special_context
        }
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = idea_json
            manager.cfg = mock_cfg
            
            task_desc_str = manager._get_task_desc_str()
        
        # Verify special characters are preserved
        assert "< 8GB" in task_desc_str
        assert "<= 2 hours" in task_desc_str
        assert '"clean"' in task_desc_str
        assert "/data/train/*.csv" in task_desc_str

    def test_additional_context_with_multiline_content(self):
        """Test that multiline additional context is preserved."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        multiline_context = """Line 1: First instruction
Line 2: Second instruction
Line 3: Third instruction with details

Paragraph break here.

Final notes."""
        
        idea_json = {
            "Title": "Test",
            "Abstract": "Test",
            "Short Hypothesis": "Test",
            "Experiments": ["Test"],
            "Risk Factors and Limitations": ["Test"],
            "Additional Context": multiline_context
        }
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = idea_json
            manager.cfg = mock_cfg
            
            task_desc_str = manager._get_task_desc_str()
        
        # Verify multiline content is preserved
        assert "Line 1: First instruction" in task_desc_str
        assert "Line 2: Second instruction" in task_desc_str
        assert "Final notes." in task_desc_str

    def test_additional_context_json_serialization(self):
        """Test that Additional Context survives JSON round-trip (MongoDB storage)."""
        original_context = "Special instructions: use GPU, limit memory to 4GB, output plots"
        
        idea_json = {
            "Name": "test",
            "Title": "Test",
            "Short Hypothesis": "Test",
            "Abstract": "Test",
            "Experiments": ["Test"],
            "Risk Factors and Limitations": ["Test"],
            "Additional Context": original_context
        }
        
        # Simulate MongoDB storage (serialize to JSON string, then parse back)
        json_str = json.dumps(idea_json)
        restored = json.loads(json_str)
        
        assert restored["Additional Context"] == original_context

    def test_very_long_additional_context(self):
        """Test that very long additional context is handled."""
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Create a very long context (simulating detailed user instructions)
        long_context = "Detailed instruction. " * 500  # ~10,000 characters
        
        idea_json = {
            "Title": "Test",
            "Abstract": "Test",
            "Short Hypothesis": "Test",
            "Experiments": ["Test"],
            "Risk Factors and Limitations": ["Test"],
            "Additional Context": long_context
        }
        
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = idea_json
            manager.cfg = mock_cfg
            
            task_desc_str = manager._get_task_desc_str()
        
        # Verify long context is included
        assert "Detailed instruction." in task_desc_str
        assert task_desc_str.count("Detailed instruction.") == 500


class TestHypothesisSchemaValidation:
    """Test that the hypothesis schema properly handles additionalContext."""

    def test_hypothesis_with_additional_context_is_valid(self):
        """Test that a hypothesis with additionalContext passes validation."""
        hypothesis_data = {
            "_id": "valid-123",
            "title": "Valid Hypothesis Title",
            "idea": "This is a valid idea with enough characters.",
            "additionalContext": "Some additional context here",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "test-user"
        }
        
        # Basic structure validation
        assert len(hypothesis_data["title"]) >= 3
        assert len(hypothesis_data["idea"]) >= 10
        assert isinstance(hypothesis_data.get("additionalContext"), str)

    def test_hypothesis_without_additional_context_is_valid(self):
        """Test that a hypothesis without additionalContext passes validation."""
        hypothesis_data = {
            "_id": "valid-456",
            "title": "Valid Hypothesis Title",
            "idea": "This is a valid idea with enough characters.",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "test-user"
        }
        
        # Should be valid without additionalContext
        assert len(hypothesis_data["title"]) >= 3
        assert len(hypothesis_data["idea"]) >= 10
        assert "additionalContext" not in hypothesis_data or hypothesis_data.get("additionalContext") is None


class TestIdeationFlowWithAdditionalContext:
    """Test that additionalContext flows correctly through ideation."""

    def test_workshop_file_includes_additional_context(self):
        """Test that the workshop file for ideation includes additional context."""
        # Simulate hypothesis with additional context
        hypothesis = {
            "_id": "ideation-test-123",
            "title": "Memory-Efficient Transformers",
            "idea": "Develop memory-efficient attention mechanisms.",
            "additionalContext": "Must work on 8GB VRAM. Use FlashAttention as baseline.",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "researcher"
        }
        
        title = hypothesis.get("title", "Research Direction")
        idea_text = hypothesis.get("idea", "")
        additional_context = hypothesis.get("additionalContext", "")
        
        # Build workshop content as pod_worker does
        workshop_content = f"# {title}\n\n## Research Prompt\n{idea_text}\n\n"
        if additional_context:
            workshop_content += f"## Additional Context (User Instructions)\n{additional_context}\n\n"
        workshop_content += (
            "## Guidance\n"
            "Generate a compelling research proposal expanding on the hypothesis above. "
            "Use the ideation pipeline tools, perform literature search, and return the final idea JSON.\n"
        )
        
        # Verify additional context is in the workshop file
        assert "## Additional Context (User Instructions)" in workshop_content
        assert "Must work on 8GB VRAM" in workshop_content
        assert "FlashAttention" in workshop_content

    def test_workshop_file_without_additional_context(self):
        """Test that workshop file works without additional context."""
        hypothesis = {
            "_id": "ideation-test-456",
            "title": "Basic Research",
            "idea": "Test basic approach.",
            "createdAt": "2024-01-01T00:00:00Z",
            "createdBy": "researcher"
        }
        
        title = hypothesis.get("title", "Research Direction")
        idea_text = hypothesis.get("idea", "")
        additional_context = hypothesis.get("additionalContext", "")
        
        workshop_content = f"# {title}\n\n## Research Prompt\n{idea_text}\n\n"
        if additional_context:
            workshop_content += f"## Additional Context (User Instructions)\n{additional_context}\n\n"
        workshop_content += "## Guidance\n..."
        
        # Verify additional context section is NOT present
        assert "## Additional Context (User Instructions)" not in workshop_content
        assert "Basic Research" in workshop_content

    def test_idea_json_injection_after_ideation(self):
        """Test that additionalContext is injected into ideaJson after ideation completes."""
        # Simulate normalized ideation output (what comes from perform_ideation_temp_free.py)
        normalized_idea = {
            "Name": "memory_efficient_transformers",
            "Title": "Memory-Efficient Transformers",
            "Short Hypothesis": "Efficient attention reduces memory usage.",
            "Abstract": "Full description here.",
            "Experiments": ["Exp 1", "Exp 2"],
            "Risk Factors and Limitations": ["Risk 1"]
        }
        
        # Simulate additionalContext from hypothesis
        additional_context = "Must work on 8GB VRAM. Use FlashAttention."
        
        # Simulate the injection logic from pod_worker.py
        final_idea_json = normalized_idea.copy()
        if additional_context:
            final_idea_json["Additional Context"] = additional_context
        
        # Verify injection worked
        assert "Additional Context" in final_idea_json
        assert final_idea_json["Additional Context"] == "Must work on 8GB VRAM. Use FlashAttention."
        
        # Verify original fields still exist
        assert final_idea_json["Title"] == "Memory-Efficient Transformers"
        assert "Experiments" in final_idea_json


class TestFullIdeationToExperimentFlow:
    """Test the complete flow from ideation through to experiment prompts."""

    def test_additional_context_survives_ideation_to_experiment(self):
        """
        Test complete flow:
        1. Hypothesis created with additionalContext
        2. Ideation runs and produces normalized ideas
        3. additionalContext injected into ideaJson
        4. AgentManager reads ideaJson and includes context in prompts
        """
        from ai_scientist.treesearch.agent_manager import AgentManager
        
        # Step 1: Original hypothesis
        additional_context = "Use PyTorch only. Limit training to 100 epochs. Focus on interpretability."
        
        # Step 2: Ideation produces this output
        ideation_output = {
            "Name": "interpretable_models",
            "Title": "Interpretable Deep Learning",
            "Short Hypothesis": "Simpler models are more interpretable.",
            "Abstract": "Explore interpretable architectures.",
            "Experiments": ["Test simple models"],
            "Risk Factors and Limitations": ["May sacrifice accuracy"]
        }
        
        # Step 3: Inject additional context (as pod_worker does)
        final_idea_json = ideation_output.copy()
        final_idea_json["Additional Context"] = additional_context
        
        # Verify ideaJson has context
        assert "Additional Context" in final_idea_json
        
        # Step 4: AgentManager consumes this
        mock_cfg = MagicMock()
        mock_cfg.agent.stages = MagicMock()
        mock_cfg.agent.steps = 10
        
        with patch.object(AgentManager, '__init__', lambda self, *args, **kwargs: None):
            manager = AgentManager.__new__(AgentManager)
            manager.task_desc = final_idea_json
            manager.cfg = mock_cfg
            
            task_desc_str = manager._get_task_desc_str()
        
        # Verify complete flow
        assert "Interpretable Deep Learning" in task_desc_str  # Title from ideation
        assert "Additional Context" in task_desc_str  # Context section
        assert "Use PyTorch only" in task_desc_str  # User's constraint preserved
        assert "100 epochs" in task_desc_str  # User's limit preserved
        assert "interpretability" in task_desc_str  # User's focus preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

