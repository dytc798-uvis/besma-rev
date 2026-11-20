using System.Collections;
using System.Windows.Automation;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
namespace Jsi.PeriodCalendar;
public static class PeriodLines
{
 public static Border Decorate(Border cell,DateTime date)
 {
  if(cell.Child is not ScrollViewer scroll||scroll.Content is not StackPanel stack)return cell;
  var periods=new List<Button>();
  foreach(var child in stack.Children)
  {
   if(child is not Button button||button.Tag is null)continue;
   var tag=button.Tag;var type=tag.GetType();
   var start=type.GetProperty("ScheduledDate")?.GetValue(tag);
   var end=type.GetProperty("DueDate")?.GetValue(tag);
   if(start is DateOnly from&&end is DateOnly until&&until>from)periods.Add(button);
  }
  var position=1;
  foreach(var button in periods)
  {
   var tag=button.Tag;var type=tag.GetType();
   var from=(DateOnly)type.GetProperty("ScheduledDate")!.GetValue(tag)!;
   var until=(DateOnly)type.GetProperty("DueDate")!.GetValue(tag)!;
   var title=(string?)type.GetProperty("Title")?.GetValue(tag)??"기간 일정";
   var status=(string?)type.GetProperty("Status")?.GetValue(tag);
   stack.Children.Remove(button);
   var color=status=="COMPLETED"?Brushes.SlateGray:Brushes.SteelBlue;
   var content=new Grid{Height=18};
   content.Children.Add(new Border{BorderBrush=color,BorderThickness=new Thickness(0,0,0,2),VerticalAlignment=VerticalAlignment.Bottom,Height=2});
   if(date.DayOfWeek==DayOfWeek.Sunday||DateOnly.FromDateTime(date)==from)
    content.Children.Add(new TextBlock{Text="기간 일정 · "+title,FontSize=10,Foreground=color,TextTrimming=TextTrimming.CharacterEllipsis,Margin=new Thickness(2,0,0,3)});
   button.Content=content;button.MinHeight=18;button.Height=18;button.Padding=new Thickness(0);button.Margin=new Thickness(-3,0,-3,0);button.BorderThickness=new Thickness(0);button.Background=Brushes.Transparent;button.HorizontalContentAlignment=HorizontalAlignment.Stretch;
   button.ToolTip=$"기간 일정 · {from:yyyy-MM-dd} ~ {until:yyyy-MM-dd}\n{title}";
   button.SetValue(AutomationProperties.NameProperty,$"기간 일정 · {title} · {from:yyyy-MM-dd} ~ {until:yyyy-MM-dd}");
   stack.Children.Insert(position++,button);
  }
  return cell;
 }
}

