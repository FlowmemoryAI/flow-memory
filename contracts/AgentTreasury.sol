// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Agent Treasury
/// @notice Minimal unaudited local treasury scaffold for testnet-oriented agent economy experiments.
contract AgentTreasury {
    address public controller;
    mapping(address => uint256) public withdrawable;

    event Deposited(address indexed payer, address indexed beneficiary, uint256 amount);
    event Withdrawn(address indexed beneficiary, uint256 amount);
    event ControllerChanged(address indexed oldController, address indexed newController);

    error NotController();
    error InvalidController();
    error NothingToWithdraw();
    error WithdrawFailed();

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

    function depositFor(address beneficiary) external payable {
        require(beneficiary != address(0), "bad beneficiary");
        require(msg.value > 0, "amount required");
        withdrawable[beneficiary] += msg.value;
        emit Deposited(msg.sender, beneficiary, msg.value);
    }

    function controllerCredit(address beneficiary, uint256 amount) external onlyController {
        require(beneficiary != address(0), "bad beneficiary");
        withdrawable[beneficiary] += amount;
        emit Deposited(msg.sender, beneficiary, amount);
    }

    function withdraw() external {
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        withdrawable[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: amount}("");
        if (!ok) revert WithdrawFailed();
        emit Withdrawn(msg.sender, amount);
    }
}
