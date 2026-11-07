export function isPhoneDevice(){return navigator.userAgentData?.mobile===true||/iPhone|iPod|Android.*Mobile|Windows Phone/i.test(navigator.userAgent);}
