// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Reputation} from "./Reputation.sol";

/// @notice Backward-compatible SBT-style alias for non-transferable reputation.
contract ReputationSBT is Reputation {
    constructor() Reputation(msg.sender) {}
}
