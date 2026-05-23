// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AgentRegistry} from "./AgentRegistry.sol";

/// @notice Backward-compatible name for the DID-focused registry.
contract AgentDIDRegistry is AgentRegistry {}
