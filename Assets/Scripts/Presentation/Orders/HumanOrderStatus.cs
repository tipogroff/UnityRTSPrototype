namespace RTS.Presentation.Orders
{
    public enum HumanOrderStatus
    {
        None,
        Pending,
        Moving,
        WaitingForStep,
        MovingToResource,
        Harvesting,
        MovingToBase,
        ReturningToBase,
        MovingToBuildSite,
        BuildingBarracks,
        MovingToAttackRange,
        Attacking,
        Completed,
        Failed,
        Cancelled
    }
}
