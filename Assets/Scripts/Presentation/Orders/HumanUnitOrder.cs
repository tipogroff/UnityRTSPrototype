using RTS.Core;
using RTS.Gameplay;

namespace RTS.Presentation.Orders
{
    public abstract class HumanUnitOrder
    {
        protected HumanUnitOrder(UnitRuntime unit, Owner owner)
        {
            Unit = unit;
            Owner = owner;
            SetStatus(HumanOrderStatus.Pending, "Order pending.");
        }

        public UnitRuntime Unit { get; }
        public Owner Owner { get; }
        public HumanOrderStatus Status { get; private set; }
        public string StatusText { get; private set; } = string.Empty;
        public string FailureReason { get; private set; } = string.Empty;
        public bool IsTerminal => Status == HumanOrderStatus.Completed
                                  || Status == HumanOrderStatus.Failed
                                  || Status == HumanOrderStatus.Cancelled;

        public abstract void TickAfterStep();

        public virtual void Cancel()
        {
            if (!IsTerminal)
            {
                SetStatus(HumanOrderStatus.Cancelled, "Order cancelled.");
            }
        }

        protected void Complete(string text)
        {
            SetStatus(HumanOrderStatus.Completed, text);
        }

        protected void Fail(string reason)
        {
            FailureReason = reason ?? "Order failed.";
            SetStatus(HumanOrderStatus.Failed, $"Order failed: {FailureReason}");
        }

        protected void SetStatus(HumanOrderStatus status, string text)
        {
            Status = status;
            StatusText = text ?? string.Empty;
        }
    }
}
