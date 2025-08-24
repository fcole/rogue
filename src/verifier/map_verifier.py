import json
import time
from typing import List, Dict, Any
from ..shared.models import MapData, VerificationResult
from ..shared.llm_client import LLMClient
from ..shared.utils import load_config, visualize_map, count_tiles, validate_map_dimensions


class MapVerifier:
    def __init__(self, config_file: str = "verifier.json"):
        self.config = load_config(config_file)
        llm_config = self.config["llm"].copy()
        provider = llm_config.pop("provider")
        self.llm = LLMClient.create(provider, **llm_config)

    def verify_maps(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify multiple map-prompt pairs."""
        results = []
        total_time = 0
        
        for test_case in test_cases:
            start_time = time.time()
            result = self._verify_single_map(test_case)
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            total_time += processing_time
            results.append(result)
        
        # Calculate summary statistics
        passed = len([r for r in results if r.passed])
        average_score = sum(r.overall_score for r in results) / len(results) if results else 0
        
        summary = {
            "total_tests": len(test_cases),
            "passed": passed,
            "failed": len(test_cases) - passed,
            "average_score": average_score,
            "common_failures": self._identify_common_failures(results)
        }
        
        return {
            "results": results,
            "summary": summary
        }

    def _verify_single_map(self, test_case: Dict[str, Any]) -> VerificationResult:
        """Verify a single map against its prompt."""
        try:
            prompt = test_case["prompt"]
            map_data = test_case["map"]
            test_id = test_case.get("test_id", "unknown")
            
            # Convert dict to MapData if needed
            if isinstance(map_data, dict):
                map_data = MapData(**map_data)
            
            # First check for critical dimension errors - these are automatic failures
            dimension_valid, dimension_errors = self._check_dimensions(map_data)
            
            # Perform quantitative checks
            quantitative_score, quantitative_details = self._quantitative_verification(
                prompt, map_data
            )
            
            # Add dimension errors to quantitative details
            if dimension_errors:
                quantitative_details["dimension_errors"] = {
                    "passed": False,
                    "errors": dimension_errors
                }
            else:
                quantitative_details["dimension_errors"] = {
                    "passed": True,
                    "errors": []
                }
            
            # Perform qualitative checks using LLM (only if dimensions are valid)
            if dimension_valid:
                qualitative_score, qualitative_details, llm_response = self._qualitative_verification(
                    prompt, map_data
                )
            else:
                # Skip expensive LLM verification for maps with dimension errors
                qualitative_score = 0.0
                qualitative_details = {"skipped": "Dimension errors prevent qualitative analysis"}
                llm_response = {"error": "Map has dimension errors, skipping LLM verification"}
            
            # Calculate overall score
            q_weight = self.config["verification"]["quantitative_weight"]
            ql_weight = self.config["verification"]["qualitative_weight"]
            overall_score = (quantitative_score * q_weight + qualitative_score * ql_weight)
            
            # CRITICAL: Maps with dimension errors automatically fail regardless of score
            if not dimension_valid:
                overall_score = 0.0
                passed = False
            else:
                # Determine if passed (simple threshold for dimensionally valid maps)
                passed = overall_score >= 6.0
            
            return VerificationResult(
                test_id=test_id,
                overall_score=overall_score,
                passed=passed,
                quantitative_checks=quantitative_details,
                qualitative_checks=qualitative_details,
                llm_response=llm_response,
                processing_time=0  # Will be set by caller
            )
            
        except Exception as e:
            return VerificationResult(
                test_id=test_case.get("test_id", "unknown"),
                overall_score=0.0,
                passed=False,
                quantitative_checks={"error": str(e)},
                qualitative_checks={"error": str(e)},
                llm_response={"error": str(e)},
                processing_time=0
            )

    def _quantitative_verification(self, prompt: str, map_data: MapData) -> tuple[float, Dict[str, Any]]:
        """Perform rule-based quantitative verification."""
        details = {}
        score = 10.0  # Start with perfect score, deduct for issues
        
        # Entity count verification
        entity_checks = self._check_entity_counts(prompt, map_data)
        details["entity_counts"] = entity_checks
        
        for check in entity_checks.values():
            if not check.get("passed", True):
                score -= 2.0  # Deduct points for failed entity checks
        
        # Map structure checks
        structure_score, structure_details = self._check_map_structure(prompt, map_data)
        details["structure"] = structure_details
        score = min(score, score * (structure_score / 10.0))
        
        # Connectivity check
        if not map_data.metadata.get("connectivity_verified", False):
            details["connectivity"] = {"passed": False, "message": "Map not fully connected"}
            score -= 3.0
        else:
            details["connectivity"] = {"passed": True, "message": "Map fully connected"}
        
        return max(0.0, score), details

    def _qualitative_verification(self, prompt: str, map_data: MapData) -> tuple[float, Dict[str, Any], Dict[str, Any]]:
        """Perform LLM-based qualitative verification."""
        try:
            # Create visualization for LLM
            visual = visualize_map(map_data)
            
            # Build verification prompt
            verification_prompt = self._build_verification_prompt(prompt, visual)
            
            # Query local LLM
            response = self.llm.query(verification_prompt)
            
            # Parse response
            llm_data = self._parse_verification_response(response)
            
            # Extract qualitative score
            confidence = llm_data.get("confidence", 5)
            qualitative_details = {
                "atmosphere_match": {
                    "score": confidence,
                    "positive_aspects": llm_data.get("positive_aspects", []),
                    "negative_aspects": llm_data.get("negative_aspects", [])
                }
            }
            
            return confidence, qualitative_details, llm_data
            
        except Exception as e:
            return 5.0, {"error": str(e)}, {"error": str(e)}

    def _check_dimensions(self, map_data: MapData) -> tuple[bool, list[str]]:
        """Check if map has correct dimensions. Returns (is_valid, error_list)."""
        return validate_map_dimensions(map_data.tiles, map_data.width, map_data.height)

    def _check_entity_counts(self, prompt: str, map_data: MapData) -> Dict[str, Any]:
        """Check if entity counts match prompt requirements."""
        checks = {}
        
        # Simple keyword matching for entity counts
        prompt_lower = prompt.lower()
        
        # Check for specific entity mentions
        entity_keywords = {
            "ogre": ["ogre", "ogres"],
            "goblin": ["goblin", "goblins"], 
            "shop": ["shop", "store", "merchant"],
            "chest": ["chest", "treasure"]
        }
        
        for entity_type, keywords in entity_keywords.items():
            actual_count = len(map_data.entities.get(entity_type, []))
            
            # Extract expected count from prompt
            expected_count = 0
            for keyword in keywords:
                if keyword in prompt_lower:
                    # Look for numbers before the keyword
                    words = prompt_lower.split()
                    for i, word in enumerate(words):
                        if keyword in word:
                            # Check previous words for numbers
                            for j in range(max(0, i-3), i):
                                try:
                                    number_word = words[j]
                                    if number_word.isdigit():
                                        expected_count = max(expected_count, int(number_word))
                                    elif number_word in ["one", "a", "an"]:
                                        expected_count = max(expected_count, 1)
                                    elif number_word == "two":
                                        expected_count = max(expected_count, 2)
                                    elif number_word == "three":
                                        expected_count = max(expected_count, 3)
                                except:
                                    pass
                            break
            
            if expected_count > 0:
                checks[entity_type] = {
                    "expected": expected_count,
                    "actual": actual_count,
                    "passed": actual_count == expected_count
                }
        
        return checks

    def _check_map_structure(self, prompt: str, map_data: MapData) -> tuple[float, Dict[str, Any]]:
        """Check map structure against prompt hints."""
        details = {}
        score = 10.0
        
        # Analyze tile distribution
        tile_counts = count_tiles(map_data.tiles)
        total_tiles = sum(tile_counts.values())
        wall_ratio = tile_counts["wall"] / total_tiles if total_tiles > 0 else 0
        
        details["wall_ratio"] = wall_ratio
        
        # Check for density hints in prompt
        prompt_lower = prompt.lower()
        if "dense" in prompt_lower or "maze" in prompt_lower:
            # Expect higher wall ratio for dense areas
            if wall_ratio < 0.4:
                score -= 2.0
                details["density_match"] = {"expected": "dense", "actual": "sparse", "passed": False}
            else:
                details["density_match"] = {"expected": "dense", "actual": "dense", "passed": True}
        elif "open" in prompt_lower or "field" in prompt_lower:
            # Expect lower wall ratio for open areas
            if wall_ratio > 0.6:
                score -= 2.0
                details["density_match"] = {"expected": "open", "actual": "dense", "passed": False}
            else:
                details["density_match"] = {"expected": "open", "actual": "open", "passed": True}
        
        return score, details

    def _build_verification_prompt(self, original_prompt: str, visualization: str) -> str:
        """Build the verification prompt for the local LLM."""
        return f"""Original request: "{original_prompt}"

Generated map analysis:
{visualization}

Please evaluate if this map matches the original request. Consider:
1. Do the entity types and counts match?
2. Does the map structure fit the description? 
3. Are entities placed logically?
4. Does the overall atmosphere match?

Respond with JSON only:
{{
  "matches_request": true/false,
  "confidence": 1-10,
  "positive_aspects": ["aspect1", "aspect2"],
  "negative_aspects": ["issue1", "issue2"]
}}"""

    def _parse_verification_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM verification response."""
        try:
            # Clean up response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback parsing for non-JSON responses
            return {
                "matches_request": "yes" in response.lower(),
                "confidence": 5,
                "positive_aspects": [],
                "negative_aspects": ["Failed to parse LLM response"]
            }

    def _identify_common_failures(self, results: List[VerificationResult]) -> List[str]:
        """Identify common failure patterns across results."""
        common_failures = []
        
        # Count dimension failures (most critical)
        dimension_failures = sum(1 for r in results
                               if not r.quantitative_checks.get("dimension_errors", {}).get("passed", True))
        if dimension_failures > len(results) * 0.3:
            common_failures.append("dimension_errors")
        
        # Count entity-related failures
        entity_failures = sum(1 for r in results 
                             if any(not check.get("passed", True) 
                                   for check in r.quantitative_checks.get("entity_counts", {}).values()))
        if entity_failures > len(results) * 0.3:
            common_failures.append("entity_placement")
        
        # Count connectivity failures
        connectivity_failures = sum(1 for r in results
                                  if not r.quantitative_checks.get("connectivity", {}).get("passed", True))
        if connectivity_failures > len(results) * 0.3:
            common_failures.append("connectivity")
        
        return common_failures