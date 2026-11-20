using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
class Program
{
 [STAThread]static void Main(string[] args)
 {
  var root=@"D:\JSI\safety-workbench\dist\SafetyWorkbenchShell-current\modules\SafetyTeamDesk";
  AssemblyLoadContext.Default.Resolving+=(_,n)=>{var p=System.IO.Path.Combine(root,n.Name+".dll");return System.IO.File.Exists(p)?AssemblyLoadContext.Default.LoadFromAssemblyPath(p):null;};
  var asm=AssemblyLoadContext.Default.LoadFromAssemblyPath(System.IO.Path.GetFullPath(args[0]));
  var decorate=asm.GetType("Jsi.PeriodCalendar.PeriodLines")!.GetMethod("Decorate")!;
  int clicked=0;var date=new Button{Content="2"};var normal=new Button{Content="현장점검",Tag=new Item(new(2026,11,2),null,"현장점검","PLANNED")};
  var tag=new Item(new(2026,11,2),new(2026,11,30),"26년 하반기 평가","IN_PROGRESS");var period=new Button{Tag=tag,Content="old repeating card",MinHeight=24};period.Click+=(_,_)=>clicked++;
  var stack=new StackPanel();stack.Children.Add(date);stack.Children.Add(normal);stack.Children.Add(period);var cell=new Border{Child=new ScrollViewer{Content=stack}};
  if(!ReferenceEquals(cell,decorate.Invoke(null,[cell,new DateTime(2026,11,2)])))throw new Exception("CELL_REPLACED");
  if(period.Height!=18||period.MinHeight!=18||period.BorderThickness!=new Thickness(0)||!ReferenceEquals(period.Tag,tag))throw new Exception("PERIOD_STYLE_OR_DATA_CHANGED");
  if(normal.Content.ToString()!="현장점검"||normal.MinHeight==18)throw new Exception("DAILY_CARD_CHANGED");
  if(stack.Children[1]!=period||period.Content is not Grid first||first.Children.OfType<TextBlock>().Single().Text!="기간 일정 · 26년 하반기 평가")throw new Exception("START_LABEL_MISSING");
  period.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));if(clicked!=1)throw new Exception("DETAIL_HANDLER_LOST");
  decorate.Invoke(null,[cell,new DateTime(2026,11,3)]);if(((Grid)period.Content).Children.OfType<TextBlock>().Any())throw new Exception("REPEATING_LABEL");
  decorate.Invoke(null,[cell,new DateTime(2026,11,8)]);if(!((Grid)period.Content).Children.OfType<TextBlock>().Any())throw new Exception("WEEK_LABEL_MISSING");
  if(tag.ScheduledDate!=new DateOnly(2026,11,2)||tag.DueDate!=new DateOnly(2026,11,30))throw new Exception("DATES_CHANGED");
  Console.WriteLine(JsonSerializer.Serialize(new{passed=true,actual_patched_assembly=true,period_height=18,date_area=true,start_and_week_labels=true,no_daily_repeat=true,detail_click_preserved=true,daily_card_preserved=true,dates_preserved=true,GUI=false}));
 }
 public record Item(DateOnly ScheduledDate,DateOnly? DueDate,string Title,string Status);
}
