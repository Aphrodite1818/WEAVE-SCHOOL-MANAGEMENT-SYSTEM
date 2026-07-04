import { useContext } from "react";
import { SubscriptionContext } from "./subscriptionContext";

export const useSubscription = () => useContext(SubscriptionContext);

export default useSubscription;
