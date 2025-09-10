package lx.edu.springmvc.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
public class HelloController {

	@RequestMapping("/hello.do")
	public String hello() {
		return "hello";
	}
	
	@RequestMapping("/hello_feat_list.do")
	public String hello_feat_list() {
		return "hello";
	}
	
}
