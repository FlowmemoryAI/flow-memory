// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Non-Transferable Reputation
/// @notice Controller-gated, non-transferable reputation scores keyed by agentId.
contract Reputation {
    struct ReputationRecord {
        int256 score;
        uint64 positiveEvents;
        uint64 negativeEvents;
        uint64 updatedAt;
    }

    address public controller;
    mapping(bytes32 => ReputationRecord) private records;

    event ControllerChanged(address indexed oldController, address indexed newController);
    event ReputationChanged(bytes32 indexed agentId, int256 delta, int256 score, bytes32 evidenceHash);

    error NotController();
    error InvalidController();

    modifier onlyController() {
        if (msg.sender != controller) revert NotController();
        _;
    }

    constructor(address initialController) {
        if (initialController == address(0)) revert InvalidController();
        controller = initialController;
        emit ControllerChanged(address(0), initialController);
    }

    function setController(address newController) external onlyController {
        if (newController == address(0)) revert InvalidController();
        address old = controller;
        controller = newController;
        emit ControllerChanged(old, newController);
    }

    function applyDelta(bytes32 agentId, int256 delta, bytes32 evidenceHash) external onlyController {
        ReputationRecord storage record = records[agentId];
        record.score += delta;
        if (delta >= 0) {
            record.positiveEvents += 1;
        } else {
            record.negativeEvents += 1;
        }
        record.updatedAt = uint64(block.timestamp);
        emit ReputationChanged(agentId, delta, record.score, evidenceHash);
    }

    function getReputation(bytes32 agentId) external view returns (ReputationRecord memory) {
        return records[agentId];
    }

    // Intentionally no ERC-20/721 transfer surface: reputation is non-transferable by design.
}
